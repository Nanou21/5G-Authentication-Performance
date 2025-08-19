#!/usr/bin/env python3
"""
Automated 5G Authentication Performance Test Orchestrator
Runs multiple test iterations and consolidates results
"""

import subprocess
import time
import os
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import yaml
import argparse

class TestOrchestrator:
    def __init__(self, config_file=None):
        # Load configuration from YAML if provided, otherwise use defaults
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        else:
            self.load_default_config()
        
        self.results_dir = f"{self.config['output']['results_dir_prefix']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.setup_logging()
        self.test_results = []
    
    def load_config(self, config_file):
        """Load configuration from YAML file"""
        try:
            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f)
            
            # Extract test parameters
            test_config = self.config['test_configuration']
            self.auth_methods = test_config['authentication_methods']
            self.ue_counts = test_config['ue_counts']
            self.iterations = test_config['iterations_per_test']
            
            print(f"Loaded configuration from {config_file}")
            
        except Exception as e:
            print(f"Error loading config file {config_file}: {e}")
            print("Using default configuration instead")
            self.load_default_config()
    
    def load_default_config(self):
        """Load default configuration if no YAML file provided"""
        self.config = {
            'test_configuration': {
                'authentication_methods': ['5G_AKA', 'EAP_AKA'],
                'ue_counts': [10, 25, 50, 75, 100],
                'iterations_per_test': 3
            },
            'timing': {
                'service_restart_wait': 15,
                'gnb_startup_wait': 10,
                'ue_settlement_wait': 5,
                'test_duration_base': 60,
                'test_duration_per_ue': 0.5,
                'cleanup_wait': 5,
                'inter_test_wait': 30
            },
            'scripts': {
                'change_auth': 'python3 change_authmethod.py',
                'start_services': 'sudo bash startservices.sh',
                'add_subscribers': 'sudo python3 add_subscribers.py',
                'start_gnb': 'sudo bash start_gnb.sh',
                'launch_ues': 'sudo bash launch_ues.sh',
                'monitor_performance': 'sudo python3 Memoryusage.py',
                'cleanup_ues': 'pkill nr-ue'
            },
            'output': {
                'results_dir_prefix': 'automated_test_results',
                'result_file_name': 'registration_overhead_summary.csv',
                'log_level': 'INFO',
                'generate_plots': True,
                'consolidate_results': True
            },
            'error_handling': {
                'max_retries': 2,
                'timeout_seconds': 300,
                'continue_on_failure': True,
                'cleanup_on_error': True
            }
        }
        
        # Extract test parameters
        test_config = self.config['test_configuration']
        self.auth_methods = test_config['authentication_methods']
        self.ue_counts = test_config['ue_counts']
        self.iterations = test_config['iterations_per_test']
        
    def setup_logging(self):
        """Setup logging configuration"""
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Get log level from config
        log_level = getattr(logging, self.config['output']['log_level'].upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{self.results_dir}/test_orchestrator.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def run_command(self, command, timeout=None):
        """Execute shell command with timeout and error handling"""
        if timeout is None:
            timeout = self.config['error_handling']['timeout_seconds']
            
        try:
            self.logger.info(f"Executing: {command}")
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            if result.returncode != 0:
                self.logger.error(f"Command failed: {command}")
                self.logger.error(f"Error: {result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out: {command}")
            return False
        except Exception as e:
            self.logger.error(f"Exception running command {command}: {e}")
            return False
    
    def cleanup_processes(self):
        """Kill any running UE processes"""
        self.logger.info("Cleaning up UE processes")
        cleanup_cmd = self.config['scripts']['cleanup_ues']
        subprocess.run(cleanup_cmd, shell=True, capture_output=True)
        time.sleep(self.config['timing']['cleanup_wait'])
    
    def restart_services(self):
        """Restart 5G core services"""
        self.logger.info("Restarting core services")
        self.cleanup_processes()
        
        # Stop services (adjust based on your setup)
        # subprocess.run("sudo systemctl stop open5gs-*", shell=True, capture_output=True)
        time.sleep(self.config['timing']['ue_settlement_wait'])
        
        # Start services
        start_cmd = self.config['scripts']['start_services']
        if not self.run_command(start_cmd):
            raise Exception("Failed to start services")
        time.sleep(self.config['timing']['service_restart_wait'])
    
    def run_single_test(self, auth_method, ue_count, iteration):
        """Run a single test configuration"""
        test_name = f"{auth_method}_{ue_count}ues_iter{iteration}"
        test_dir = os.path.join(self.results_dir, test_name)
        os.makedirs(test_dir, exist_ok=True)
        
        self.logger.info(f"Starting test: {test_name}")
        
        try:
            # Set authentication method
            change_auth_cmd = f"{self.config['scripts']['change_auth']} {auth_method}"
            if not self.run_command(change_auth_cmd):
                raise Exception(f"Failed to set auth method to {auth_method}")
            
            # Restart services for new auth method
            self.restart_services()
            
            # Add subscribers
            add_subs_cmd = f"{self.config['scripts']['add_subscribers']} {ue_count}"
            if not self.run_command(add_subs_cmd):
                raise Exception(f"Failed to add {ue_count} subscribers")
            
            # Start gNodeB
            gnb_cmd = self.config['scripts']['start_gnb']
            gnb_process = subprocess.Popen(
                gnb_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(self.config['timing']['gnb_startup_wait'])
            
            # Start performance monitoring
            monitor_log = os.path.join(test_dir, "performance_output.log")
            monitor_cmd = f"{self.config['scripts']['monitor_performance']} > {monitor_log} 2>&1"
            monitor_process = subprocess.Popen(monitor_cmd, shell=True)
            
            # Record start time
            start_time = time.time()
            
            # Launch UEs
            launch_ues_cmd = f"{self.config['scripts']['launch_ues']} {ue_count}"
            if not self.run_command(launch_ues_cmd):
                self.logger.warning(f"UE launch may have failed for {ue_count} UEs")
            
            # Calculate test duration from config
            test_duration = (self.config['timing']['test_duration_base'] + 
                           ue_count * self.config['timing']['test_duration_per_ue'])
            
            self.logger.info(f"Running test for {test_duration} seconds")
            time.sleep(test_duration)
            
            # Record end time
            end_time = time.time()
            test_duration_actual = end_time - start_time
            
            # Stop monitoring
            monitor_process.terminate()
            monitor_process.wait(timeout=10)
            
            # Copy results if they exist
            result_file = self.config['output']['result_file_name']
            if os.path.exists(result_file):
                dest_file = os.path.join(test_dir, result_file)
                subprocess.run(f"cp {result_file} {dest_file}", shell=True)
                self.logger.info(f"Results copied to {dest_file}")
                
                # Parse results
                test_result = self.parse_test_results(dest_file, auth_method, ue_count, iteration, test_duration_actual)
                if test_result:
                    self.test_results.append(test_result)
            else:
                self.logger.warning(f"No results file found for {test_name}")
            
            # Cleanup
            self.cleanup_processes()
            gnb_process.terminate()
            gnb_process.wait(timeout=10)
            
            self.logger.info(f"Completed test: {test_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Test {test_name} failed: {e}")
            if self.config['error_handling']['cleanup_on_error']:
                self.cleanup_processes()
            return False
    
    def parse_test_results(self, result_file, auth_method, ue_count, iteration, duration):
        """Parse results from CSV file"""
        try:
            df = pd.read_csv(result_file)
            if not df.empty:
                # Extract key metrics (adjust based on your CSV structure)
                avg_time = df['processing_time'].mean() if 'processing_time' in df.columns else None
                max_cpu = df['cpu_usage'].max() if 'cpu_usage' in df.columns else None
                avg_memory = df['memory_usage'].mean() if 'memory_usage' in df.columns else None
                
                return {
                    'auth_method': auth_method,
                    'ue_count': ue_count,
                    'iteration': iteration,
                    'test_duration': duration,
                    'avg_processing_time': avg_time,
                    'max_cpu_usage': max_cpu,
                    'avg_memory_usage': avg_memory,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            self.logger.error(f"Failed to parse results from {result_file}: {e}")
        return None
    
    def run_all_tests(self):
        """Run all test combinations"""
        total_tests = len(self.auth_methods) * len(self.ue_counts) * self.iterations
        current_test = 0
        
        self.logger.info(f"Starting {total_tests} tests")
        self.logger.info(f"Auth methods: {self.auth_methods}")
        self.logger.info(f"UE counts: {self.ue_counts}")
        self.logger.info(f"Iterations: {self.iterations}")
        
        for auth_method in self.auth_methods:
            for ue_count in self.ue_counts:
                for iteration in range(1, self.iterations + 1):
                    current_test += 1
                    self.logger.info(f"Progress: Test {current_test}/{total_tests}")
                    
                    success = self.run_single_test(auth_method, ue_count, iteration)
                    
                    if not success and not self.config['error_handling']['continue_on_failure']:
                        self.logger.error("Test failed and continue_on_failure is False, stopping")
                        return
                    elif not success:
                        self.logger.error("Test failed, continuing with next test")
                    
                    # Rest between tests
                    if current_test < total_tests:
                        wait_time = self.config['timing']['inter_test_wait']
                        self.logger.info(f"Resting {wait_time} seconds before next test")
                        time.sleep(wait_time)
        
        self.logger.info("All tests completed")
        self.generate_summary_report()
    
    def generate_summary_report(self):
        """Generate summary report and visualizations"""
        if not self.test_results:
            self.logger.warning("No test results to summarize")
            return
        
        # Save raw results to JSON
        results_file = os.path.join(self.results_dir, "consolidated_results.json")
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        # Create DataFrame for analysis
        df = pd.DataFrame(self.test_results)
        
        # Generate CSV summary
        csv_file = os.path.join(self.results_dir, "test_summary.csv")
        df.to_csv(csv_file, index=False)
        
        # Generate basic statistics
        summary_stats = df.groupby(['auth_method', 'ue_count']).agg({
            'avg_processing_time': ['mean', 'std'],
            'max_cpu_usage': ['mean', 'std'],
            'avg_memory_usage': ['mean', 'std']
        }).round(4)
        
        stats_file = os.path.join(self.results_dir, "summary_statistics.csv")
        summary_stats.to_csv(stats_file)
        
        # Generate plots if matplotlib is available
        if self.config['output']['generate_plots']:
            try:
                self.generate_plots(df)
            except Exception as e:
                self.logger.error(f"Failed to generate plots: {e}")
        
        self.logger.info(f"Summary report generated in {self.results_dir}")
    
    def generate_plots(self, df):
        """Generate performance comparison plots"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Processing time comparison
        for auth_method in self.auth_methods:
            data = df[df['auth_method'] == auth_method]
            grouped = data.groupby('ue_count')['avg_processing_time'].mean()
            axes[0, 0].plot(grouped.index, grouped.values, marker='o', label=auth_method)
        
        axes[0, 0].set_title('Average Processing Time by UE Count')
        axes[0, 0].set_xlabel('Number of UEs')
        axes[0, 0].set_ylabel('Processing Time (s)')
        axes[0, 0].legend()
        axes[0, 0].grid(True)
        
        # CPU usage comparison
        for auth_method in self.auth_methods:
            data = df[df['auth_method'] == auth_method]
            grouped = data.groupby('ue_count')['max_cpu_usage'].mean()
            axes[0, 1].plot(grouped.index, grouped.values, marker='o', label=auth_method)
        
        axes[0, 1].set_title('Maximum CPU Usage by UE Count')
        axes[0, 1].set_xlabel('Number of UEs')
        axes[0, 1].set_ylabel('CPU Usage (%)')
        axes[0, 1].legend()
        axes[0, 1].grid(True)
        
        # Memory usage comparison
        for auth_method in self.auth_methods:
            data = df[df['auth_method'] == auth_method]
            grouped = data.groupby('ue_count')['avg_memory_usage'].mean()
            axes[1, 0].plot(grouped.index, grouped.values, marker='o', label=auth_method)
        
        axes[1, 0].set_title('Average Memory Usage by UE Count')
        axes[1, 0].set_xlabel('Number of UEs')
        axes[1, 0].set_ylabel('Memory Usage (MB)')
        axes[1, 0].legend()
        axes[1, 0].grid(True)
        
        # Test duration
        for auth_method in self.auth_methods:
            data = df[df['auth_method'] == auth_method]
            grouped = data.groupby('ue_count')['test_duration'].mean()
            axes[1, 1].plot(grouped.index, grouped.values, marker='o', label=auth_method)
        
        axes[1, 1].set_title('Test Duration by UE Count')
        axes[1, 1].set_xlabel('Number of UEs')
        axes[1, 1].set_ylabel('Duration (s)')
        axes[1, 1].legend()
        axes[1, 1].grid(True)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.results_dir, 'performance_comparison.png'), dpi=300)
        plt.close()

def main():
    parser = argparse.ArgumentParser(description='5G Authentication Performance Test Orchestrator')
    parser.add_argument('--config', '-c', type=str, default=None, 
                       help='Path to YAML configuration file (optional)')
    parser.add_argument('--auth-methods', type=str, nargs='+', 
                       help='Authentication methods to test (overrides config)')
    parser.add_argument('--ue-counts', type=int, nargs='+', 
                       help='UE counts to test (overrides config)')
    parser.add_argument('--iterations', type=int, 
                       help='Number of iterations per test (overrides config)')
    
    args = parser.parse_args()
    
    # Create orchestrator with config file
    orchestrator = TestOrchestrator(config_file=args.config)
    
    # Override with command line arguments if provided
    if args.auth_methods:
        orchestrator.auth_methods = args.auth_methods
    if args.ue_counts:
        orchestrator.ue_counts = args.ue_counts
    if args.iterations:
        orchestrator.iterations = args.iterations
    
    try:
        orchestrator.run_all_tests()
    except KeyboardInterrupt:
        orchestrator.logger.info("Tests interrupted by user")
        orchestrator.cleanup_processes()
    except Exception as e:
        orchestrator.logger.error(f"Test orchestration failed: {e}")
        orchestrator.cleanup_processes()

if __name__ == "__main__":
    main()