#!/usr/bin/env python3
"""
Automated 5G Authentication Performance Test Orchestrator
Runs multiple test iterations and consolidates results
"""
import io
import subprocess
import time
import os
import json
import logging
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import yaml
import argparse
import shlex
from scipy.stats import ttest_ind
import numpy as np

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
            'remote_core': {
                'enabled': True,
                'user': "gcore1",
                'host': "192.168.0.6",
                'ssh_key': "~/.ssh/id_rsa",
                'remote_results_dir': "/home/gcore1/open5gs/5G-Authentication-Performance/results",   # ✅ REQUIRED
                'monitor_script_path': "/home/gcore1/open5gs/5G-Authentication-Performance/Memoryusage.py",  # ✅ REQUIRED
                'amf_log_path': "/var/log/open5gs/amf.log",  # ✅ REQUIRED
                'monitor_interval': 0.1  # ✅ OPTIONAL (default fallback)
            },
            'test_configuration': {
                'authentication_methods': ['5G_AKA', 'EAP_AKA'],
                'ue_counts': [10, 25, 40, 55, 70, 85, 100],
                'iterations_per_test': 10
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
                'change_auth': {'command': 'python3 /home/gcore1/open5gs/5G-Authentication-Performance/change_authmethod.py', 'location': 'core'},
                'start_services': {'command': 'echo "1234" | sudo -S bash /home/gcore1/open5gs/5G-Authentication-Performance/startservices.sh', 'location': 'core'},
                'add_subscribers': {'command': 'echo "1234" | sudo -S python3 /home/gcore1/open5gs/5G-Authentication-Performance/add_subscribers.py', 'location': 'core'},
                'start_gnb': {'command': 'sudo bash start_gnb.sh', 'location': 'local'},
                'launch_ues': {'command': 'sudo bash ./launch_ues.sh', 'location': 'local'},
                # 'monitor_performance': {'command': 'echo "1234" | sudo -S python3 /home/gcore1/open5gs/5G-Authentication-Performance/Memoryusage.py', 'location': 'core'},
                'cleanup_ues': {'command': 'sudo pkill nr-ue', 'location': 'local'}
            },
            'output': {
                'results_dir_prefix': 'automated_5g_tests',
                'result_file_name': 'registration_overhead_summary.csv',
                'log_level': 'INFO',
                'generate_plots': True,
                'consolidate_results': True
            },
            'monitoring': {'enabled': True, 'cpu_monitoring': True, 'memory_monitoring': True, 'network_monitoring': False, 'disk_monitoring': False},
            'error_handling': {'max_retries': 2, 'timeout_seconds': 300, 'continue_on_failure': True, 'cleanup_on_error': True},
            'advanced': {'parallel_monitoring': False, 'custom_test_duration': False, 'save_intermediate_logs': True, 'compress_results': False}
        }

        test_config = self.config['test_configuration']
        self.auth_methods = test_config['authentication_methods']
        self.ue_counts = test_config['ue_counts']
        self.iterations = test_config['iterations_per_test']
    def run_background(command):
        return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def setup_logging(self):
        """Setup logging configuration"""
        os.makedirs(self.results_dir, exist_ok=True)
        log_level = getattr(logging, self.config['output']['log_level'].upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(f'{self.results_dir}/test_orchestrator.log'), logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)

    def run_command(self, script_key, extra_args=None, timeout=None, background=False, return_popen=False):
        """Execute a script command either locally or on remote Core VM via SSH"""
        if timeout is None:
            timeout = self.config['error_handling']['timeout_seconds']

        script_cfg = self.config['scripts'][script_key]
        command = script_cfg['command'] if isinstance(script_cfg, dict) else script_cfg
        location = script_cfg.get('location', 'local') if isinstance(script_cfg, dict) else 'local'

        if extra_args:
            if isinstance(extra_args, (list, tuple)):
                command += " " + " ".join(map(str, extra_args))
            else:
                command += f" {extra_args}"

        if location == "core" and self.config.get('remote_core', {}).get('enabled', False):
            user = self.config['remote_core']['user']
            host = self.config['remote_core']['host']
            ssh_key = os.path.expanduser(self.config['remote_core'].get('ssh_key', "~/.ssh/id_rsa"))
            command = f'ssh -i {shlex.quote(ssh_key)} -o StrictHostKeyChecking=no {user}@{host} "{command}"'

        try:
            if background:
                proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.logger.info(f"Started background process ({script_key}) pid={proc.pid}")
                return proc if return_popen else True

            self.logger.info(f"Executing ({location}): {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                self.logger.error(f"❌ Command failed: {command}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
                return False
            if result.stdout.strip():
                self.logger.info(f"Output:\n{result.stdout.strip()}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"⏳ Command timed out: {command}")
            return False
        except Exception as e:
            self.logger.error(f"⚠️ Exception running command {command}: {e}")
            return False


    def cleanup_processes(self):
        """Kill any running UE and gNB processes"""
        self.logger.info("Cleaning up UE and gNB processes")
        subprocess.run("sudo pkill -9 nr-ue || true", shell=True)
        subprocess.run("sudo pkill -9 nr-gnb || true", shell=True)
        time.sleep(self.config['timing']['cleanup_wait'])

    def restart_services(self):
        """Restart 5G core services with retries"""
        self.cleanup_processes()
        subprocess.run("sudo pkill -9 -f open5gs", shell=True, capture_output=True)
        time.sleep(self.config['timing']['ue_settlement_wait'])
        retries = self.config['error_handling']['max_retries']
        for attempt in range(1, retries + 1):
            self.logger.info(f"Starting services (attempt {attempt}/{retries})...")
            if self.run_command("start_services", background=True):
                time.sleep(self.config['timing']['service_restart_wait'])
                self.logger.info("✅ Core services started successfully")
                return True
            time.sleep(5)
        raise Exception("Failed to start services after multiple attempts")

    def run_single_test(self, auth_method, ue_count, iteration):
        """Run a single test configuration"""
        test_name = f"{auth_method}_{ue_count}ues_iter{iteration}"
        test_dir = os.path.join(self.results_dir, test_name)
        os.makedirs(test_dir, exist_ok=True)

        self.logger.info(f"Starting test: {test_name}")

        try:
            # ---- Configure Core ----
            if not self.run_command("change_auth", extra_args=auth_method):
                raise Exception(f"Failed to set auth method to {auth_method}")
            if not self.restart_services():
                raise Exception("Failed to restart core services")
            if not self.run_command("add_subscribers", extra_args=ue_count):
                raise Exception(f"Failed to add {ue_count} subscribers")
            if not self.run_command("start_gnb", background=True):
                raise Exception("Failed to start gNB")

            self.logger.info("Waiting for gNB to register with AMF...")
            time.sleep(self.config['timing']['gnb_startup_wait'])

            gnb_check = subprocess.run(
                "pgrep -a nr-gnb", shell=True, capture_output=True, text=True
            )
            if gnb_check.returncode != 0:
                raise Exception("gNB process not running after startup")
        

            # ---- Start remote monitor ----
            rcfg = self.config['remote_core']
            user = rcfg['user']
            host = rcfg['host']
            ssh_key = os.path.expanduser(rcfg.get('ssh_key', "~/.ssh/id_rsa"))
            remote_dir = rcfg['remote_results_dir']
            remote_script = rcfg['monitor_script_path']
            amf_log = rcfg['amf_log_path']
            interval = rcfg.get('monitor_interval', 0.1)

            remote_csv_path = f"{remote_dir}/{test_name}_{self.config['output']['result_file_name']}"
            local_csv_path = os.path.join(test_dir, os.path.basename(remote_csv_path))

            # ---- Clean previous artifacts (CSV only) ----
            subprocess.run(
                f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
                f'"mkdir -p {remote_dir} && rm -f {remote_csv_path}"',
                shell=True,
                check=True
            )

            monitor_cmd = (
                f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
                f'"python3 {remote_script} '
                f'--output {remote_csv_path} '
                f'--num-ues {ue_count} '
                f'--log {amf_log} '
                f'--interval {interval}"'
            )

            self.logger.info("Starting remote monitor")
            subprocess.Popen(monitor_cmd, shell=True)

            # ---- Launch UEs ----
            if not self.run_command("launch_ues", extra_args=ue_count):
                raise Exception(f"Failed to launch {ue_count} UEs")


            # ---- Wait for CSV to exist and be non empty ----
            self.logger.info("Waiting for remote CSV to be created...")
            wait_csv_cmd = (
                f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
                f'"timeout 60s bash -c \'while [ ! -s {remote_csv_path} ]; do sleep 1; done\'"'
            )

            if subprocess.run(wait_csv_cmd, shell=True).returncode != 0:
                raise Exception("Timeout waiting for remote CSV")

            # ---- Stop UEs AFTER monitor finishes ----
            self.run_command("cleanup_ues")

            # ---- Wait for registration to finish ----
            # test_duration = self.config["timing"]["test_duration_base"] + ue_count * self.config["timing"]["test_duration_per_ue"]
            # self.logger.info(f"Running test for {test_duration:.1f} seconds...")
            # time.sleep(test_duration)

            # ---- Fetch CSV ----
            scp_cmd = (
                f"scp -i {ssh_key} -o StrictHostKeyChecking=no "
                f"{user}@{host}:{remote_csv_path} {local_csv_path}"
            )
            self.logger.info("Copying remote CSV to local directory")

            if subprocess.run(scp_cmd, shell=True).returncode != 0:
                raise Exception("Failed to SCP remote CSV")

            if not os.path.exists(local_csv_path):
                raise Exception("CSV missing after SCP")

            # ---- Parse results ----
            result = self.parse_test_results(
                result_file=local_csv_path,
                auth_method=auth_method,
                ue_count=ue_count,
                iteration=iteration,
                duration=None
            )

            if result:
                self.test_results.append(result)
                self.logger.info(f"✅ Test completed successfully: {auth_method}, {ue_count} UEs")

            return True

        except Exception as e:
            self.logger.error(f"❌ Test failed: {e}")
            if self.config["error_handling"]["cleanup_on_error"]:
                self.cleanup_processes()
            return False


    def parse_test_results(self, result_file, auth_method, ue_count, iteration, duration):

        fallback = {
            'auth_method': auth_method,
            'ue_count': ue_count,
            'iteration': iteration,
            'test_duration': duration,
            'avg_ue_registration_time_sec': None,
            'max_cpu_usage': None,
            'avg_memory_usage': None,
            'timestamp': datetime.now().isoformat()
        }

        if not result_file or not os.path.exists(result_file):
            return fallback

        df = pd.read_csv(result_file)
        if df.empty:
            return fallback

        lower = {c.lower(): c for c in df.columns}

        return {
            'auth_method': auth_method,
            'ue_count': ue_count,
            'iteration': iteration,
            'test_duration': float(df[lower['total_time_sec']].iloc[-1]),
            'avg_ue_registration_time_sec': float(df[lower['avg_ue_registration_time_sec']].iloc[-1]),
            'max_cpu_usage': float(df[lower['avg_cpu_percent']].iloc[-1]),
            'avg_memory_usage': float(df[lower['avg_memory_mb']].iloc[-1]),
            'timestamp': str(df.iloc[-1].get('timestamp', datetime.now().isoformat()))
        }


    def run_all_tests(self):
        """Run all test combinations"""
        total_tests = len(self.auth_methods) * len(self.ue_counts) * self.iterations
        current_test = 0

        self.logger.info(f"Starting {total_tests} tests")
        for auth_method in self.auth_methods:
            for ue_count in self.ue_counts:
                for iteration in range(1, self.iterations + 1):
                    current_test += 1
                    self.logger.info(f"Progress: Test {current_test}/{total_tests}")
                    success = self.run_single_test(auth_method, ue_count, iteration)
                    if not success and not self.config['error_handling']['continue_on_failure']:
                        self.logger.error("Stopping due to failure")
                        return
                    elif not success:
                        self.logger.error("Test failed, continuing with next test")
                    if current_test < total_tests:
                        time.sleep(self.config['timing']['inter_test_wait'])

        self.logger.info("All tests completed")
        self.generate_summary_report()

    def generate_summary_report(self):
        """Generate summary report and visualizations"""
        if not self.test_results:
            self.logger.warning("No test results to summarize")
            return

        results_file = os.path.join(self.results_dir, "consolidated_results.json")
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        df = pd.DataFrame(self.test_results)
        df.to_csv(os.path.join(self.results_dir, "test_summary.csv"), index=False)
        summary = (
            df
            .groupby(['auth_method', 'ue_count'])
            .agg(
                mean_reg_time=('avg_ue_registration_time_sec', 'mean'),
                std_reg_time=('avg_ue_registration_time_sec', 'std'),
                n=('avg_ue_registration_time_sec', 'count'),
                mean_cpu=('max_cpu_usage', 'mean'),
                mean_mem=('avg_memory_usage', 'mean')
            )
            .reset_index()
        )

        summary['ci_95'] = 1.96 * summary['std_reg_time'] / np.sqrt(summary['n'])

        summary.to_csv(
            os.path.join(self.results_dir, "summary_statistics_with_ci.csv"),
            index=False
        )
        # summary_stats = df.groupby(['auth_method', 'ue_count']).agg({
        #     'avg_ue_registration_time_sec': ['mean', 'std'],
        #     'max_cpu_usage': ['mean', 'std'],
        #     'avg_memory_usage': ['mean', 'std']
        # }).round(4)

        # summary_stats.to_csv(os.path.join(self.results_dir, "summary_statistics.csv"))

        if self.config['output']['generate_plots']:
            try:
                self.generate_plots(df)
            except Exception as e:
                self.logger.error(f"Failed to generate plots: {e}")
        self.compare_auth_methods(df)
        self.logger.info(f"Summary report generated in {self.results_dir}")

    def generate_plots(self, df):
        """Generate performance comparison plots"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        metrics = [
            ('avg_ue_registration_time_sec', 'Average UE Registration Time (s)'),
            ('max_cpu_usage', 'Maximum CPU Usage (%)'),
            ('avg_memory_usage', 'Average Memory Usage (MB)'),
            ('test_duration', 'Total Registration Window (s)')
        ]


        for ax, (metric, ylabel) in zip(axes.flat, metrics):
            for auth_method in self.auth_methods:
                data = df[df['auth_method'] == auth_method]
                grouped = data.groupby('ue_count')[metric].mean()
                ax.plot(grouped.index, grouped.values, marker='o', label=auth_method)
            ax.set_xlabel('Number of UEs')
            ax.set_ylabel(ylabel)
            ax.set_title(f'{ylabel} by UE Count')
            ax.legend()
            ax.grid(True)

        plt.tight_layout()
        plt.savefig(os.path.join(self.results_dir, 'performance_comparison.png'), dpi=300)
        plt.close()

    import io  # <-- at top of file

    def _read_remote_text(self, remote_path):
        """Read a remote file via SSH (no local copy)."""
        rcfg = self.config.get('remote_core', {})
        if not (remote_path and rcfg.get('enabled', False)):
            return None
        user = rcfg['user']; host = rcfg['host']
        ssh_key = os.path.expanduser(rcfg.get('ssh_key', "~/.ssh/id_rsa"))
        cmd = f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} "cat {remote_path}"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0 or not res.stdout.strip():
            self.logger.warning(f"Remote read failed or empty: {remote_path}\nSTDERR: {res.stderr.strip()}")
            return None
        return res.stdout

    def parse_remote_results(self, remote_csv_path, auth_method, ue_count, iteration, duration):

        fallback = {
            'auth_method': auth_method,
            'ue_count': ue_count,
            'iteration': iteration,
            'test_duration': duration,
            'avg_ue_registration_time_sec': None,
            'max_cpu_usage': None,
            'avg_memory_usage': None,
            'timestamp': datetime.now().isoformat()
        }

        text = self._read_remote_text(remote_csv_path)
        if not text:
            return fallback

        df = pd.read_csv(io.StringIO(text))
        if df.empty:
            return fallback

        lower = {c.lower(): c for c in df.columns}

        return {
            'auth_method': auth_method,
            'ue_count': ue_count,
            'iteration': iteration,
            'test_duration': float(df[lower['total_time_sec']].iloc[-1]),
            'avg_ue_registration_time_sec': float(df[lower['avg_ue_registration_time_sec']].iloc[-1]),
            'max_cpu_usage': float(df[lower['avg_cpu_percent']].iloc[-1]),
            'avg_memory_usage': float(df[lower['avg_memory_mb']].iloc[-1]),
            'timestamp': str(df.iloc[-1].get('timestamp', datetime.now().isoformat()))
        }

        
    def load_existing_results(self):
        """
        Load only non-empty result CSVs from the remote core results directory.
        Ignores .done files and any CSVs that do not match the expected naming scheme.
        """
        rcfg = self.config['remote_core']
        user = rcfg['user']
        host = rcfg['host']
        ssh_key = os.path.expanduser(rcfg.get('ssh_key', "~/.ssh/id_rsa"))
        remote_dir = rcfg['remote_results_dir']

        result_csv_name = self.config['output']['result_file_name']  # e.g. registration_overhead_summary.csv
        expected_suffix = f"_{result_csv_name}"                      # e.g. _registration_overhead_summary.csv

        self.logger.info("Loading existing test CSVs from remote core results directory")

        # Find only non-empty files that end with the expected suffix, and exclude any *.done
        list_cmd = (
            f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
            f'"find {remote_dir} -type f '
            f'\\( -name \'*{expected_suffix}\' -a -size +0c \\) '
            f'! -name \'*.done\'"'
        )

        res = subprocess.run(list_cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            self.logger.error(f"Remote find failed\nSTDERR: {res.stderr.strip()}")
            return

        files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if not files:
            self.logger.warning("No non-empty remote result CSV files found")
            return

        # Parse each filename safely (supports auth methods with underscores)
        for remote_csv in files:
            filename = os.path.basename(remote_csv)

            if not filename.endswith(expected_suffix):
                self.logger.warning(f"Skipping unrecognized file (wrong suffix): {filename}")
                continue

            try:
                # filename: <AUTH>_<UE>ues_iter<ITER>_<result_csv_name>
                # Example: 5G_AKA_10ues_iter3_registration_overhead_summary.csv
                stem = filename[:-len(expected_suffix)]  # remove "_registration_overhead_summary.csv"
                left, iter_str = stem.rsplit("iter", 1)
                iteration = int(iter_str)

                left = left.rstrip("_")                  # <AUTH>_<UE>ues_
                auth_method, ue_str = left.rsplit("_", 1)
                ue_count = int(ue_str.replace("ues", ""))

            except Exception as e:
                self.logger.warning(f"Skipping unrecognized file: {filename} ({e})")
                continue

            # Parse remote CSV content
            result_dict = self.parse_remote_results(
                remote_csv_path=remote_csv,
                auth_method=auth_method,
                ue_count=ue_count,
                iteration=iteration,
                duration=None
            )

            if result_dict:
                self.test_results.append(result_dict)

        self.logger.info(f"Loaded {len(self.test_results)} results from remote core")
   

    def compare_auth_methods(self, df):
        results = []

        for ue in sorted(df['ue_count'].unique()):
            aka = df[
                (df['auth_method'] == '5G_AKA') &
                (df['ue_count'] == ue)
            ]['avg_ue_registration_time_sec']

            eap = df[
                (df['auth_method'] == 'EAP_AKA') &
                (df['ue_count'] == ue)
            ]['avg_ue_registration_time_sec']

            if len(aka) < 2 or len(eap) < 2:
                continue

            t_stat, p_val = ttest_ind(aka, eap, equal_var=False)

            results.append({
                'ue_count': ue,
                'mean_5G_AKA': aka.mean(),
                'mean_EAP_AKA': eap.mean(),
                't_statistic': t_stat,
                'p_value': p_val,
                'significant': p_val < 0.05
            })

        pd.DataFrame(results).to_csv(
            os.path.join(self.results_dir, "auth_method_comparison.csv"),
            index=False
        )


def main():
    parser = argparse.ArgumentParser(description='5G Authentication Performance Test Orchestrator')
    parser.add_argument('--config', '-c', type=str, default=None, help='Path to YAML configuration file (optional)')
    parser.add_argument('--auth-methods', type=str, nargs='+', help='Authentication methods to test (overrides config)')
    parser.add_argument('--ue-counts', type=int, nargs='+', help='UE counts to test (overrides config)')
    parser.add_argument('--iterations', type=int, help='Number of iterations per test (overrides config)')
    parser.add_argument("--summary-only",
    action="store_true",
    help="Generate summary and plots from existing result CSVs only")
    args = parser.parse_args()

    orchestrator = TestOrchestrator(config_file=args.config)
    if args.auth_methods:
        orchestrator.auth_methods = args.auth_methods
    if args.ue_counts:
        orchestrator.ue_counts = args.ue_counts
    if args.iterations:
        orchestrator.iterations = args.iterations

    try:
        if args.summary_only:
            orchestrator.load_existing_results()
            orchestrator.generate_summary_report()
        else:
            orchestrator.run_all_tests()
    except KeyboardInterrupt:
        orchestrator.logger.info("Tests interrupted by user")
        orchestrator.cleanup_processes()
    except Exception as e:
        orchestrator.logger.error(f"Test orchestration failed: {e}")
        orchestrator.cleanup_processes()


if __name__ == "__main__":
    main()
