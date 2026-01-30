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
                'monitor_performance': {'command': 'echo "1234" | sudo -S python3 /home/gcore1/open5gs/5G-Authentication-Performance/Memoryusage.py', 'location': 'core'},
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

            gnb_check = subprocess.run("pgrep -a nr-gnb", shell=True, capture_output=True, text=True)
            if gnb_check.returncode != 0:
                raise Exception("gNB process not running after startup")

            if not self.run_command("launch_ues", extra_args=ue_count):
                raise Exception(f"Failed to launch {ue_count} UEs")

            # ---- Start remote monitor ----
            monitor_proc = None
            remote_csv_path = None
            local_csv_path = None

            if self.config["monitoring"]["enabled"]:
                rcfg = self.config['remote_core']
                user = rcfg['user']
                host = rcfg['host']
                ssh_key = os.path.expanduser(rcfg.get('ssh_key', "~/.ssh/id_rsa"))
                remote_dir = rcfg['remote_results_dir']
                remote_script = rcfg.get('monitor_script_path', '/home/gcore1/open5gs/5G-Authentication-Performance/Memoryusage.py')
                amf_log = rcfg.get('amf_log_path', '/home/gcore1/open5gs/install/var/log/open5gs/amf.log')
                interval = rcfg.get('monitor_interval', 0.1)

                # Remote result path
                remote_csv_path = f"{remote_dir}/{test_name}_{self.config['output']['result_file_name']}"
                local_csv_path = os.path.join(test_dir, os.path.basename(remote_csv_path))

                # Ensure remote result directory exists
                mkdir_cmd = f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} "mkdir -p {remote_dir}"'
                subprocess.run(mkdir_cmd, shell=True, check=True)

                # Clean up old output and .done added by nanou
                # cleanup_cmd = (
                #     f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
                #     f'"rm -f {remote_csv_path} {remote_csv_path}.done"'
                # )
                # subprocess.run(cleanup_cmd, shell=True, check=True)

                # Start remote monitor script
                monitor_cmd = (
                    f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
                    f'"python3 {remote_script} --output {remote_csv_path} '
                    f'--num-ues {ue_count} --log {amf_log} --interval {interval}"'
                )

                self.logger.info(f"Starting remote monitor: {monitor_cmd}")
                monitor_proc = subprocess.Popen(
                    monitor_cmd, shell=True, text=True
                )

            # ---- Wait for registration to finish ----
            test_duration = self.config["timing"]["test_duration_base"] + ue_count * self.config["timing"]["test_duration_per_ue"]
            self.logger.info(f"Running test for {test_duration:.1f} seconds...")
            time.sleep(test_duration)

            # ---- Stop UEs and monitor ----
            self.run_command("cleanup_ues")
             # Stop monitoring
            monitor_proc.terminate()
            monitor_proc.wait(timeout=10)
        # Added by nanou
            # done_file = f"{remote_csv_path}.done"
            # csv_wait_cmd = (
            # f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
            # f'"timeout 120s bash -c \'while [ ! -f {done_file} ]; do sleep 1; done\'"'
            # )

            # self.logger.info("Waiting for remote CSV file to be created...")
            # wait_result = subprocess.run(csv_wait_cmd, shell=True)
            # if wait_result.returncode != 0:
            #     self.logger.error("Timeout waiting for remote CSV file.")
            #     raise Exception("Remote monitor output CSV was never created.")
            # self.logger.info("Giving monitor a head start...")
            # time.sleep(2)

            # ---- Fetch remote CSV if it exists ----
            # Wait until remote CSV file exists AND is non-empty
            # csv_check_cmd = (
            #     f'ssh -i "{ssh_key}" -o StrictHostKeyChecking=no {user}@{host} '
            #     f'"timeout 120s bash -c \'while [ ! -s {remote_csv_path} ]; do sleep 1; done\'"'
            # )

            # self.logger.info("Waiting for remote CSV to exist and be non-empty...")
            # wait_result = subprocess.run(csv_check_cmd, shell=True)

            # if wait_result.returncode != 0:
            #     self.logger.error("Timeout waiting for non-empty remote CSV file.")
            #     raise Exception("Remote monitor output CSV was not created or is empty.")
            
            # scp_cmd = (
            # f"scp -i {ssh_key} -o StrictHostKeyChecking=no "
            # f"{user}@{host}:{remote_csv_path} {local_csv_path}"
            # )
            # self.logger.info(f"Copying remote CSV to local dir: {scp_cmd}")
            # scp_result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)

            # if scp_result.returncode != 0:
            #     self.logger.error(f"SCP failed: {scp_result.stderr.strip()}")
            #     raise Exception("Failed to copy remote CSV")

            # if not os.path.exists(local_csv_path):
            #     raise Exception("Remote monitor output file not found after SCP.")


            if remote_csv_path and local_csv_path:
                scp_cmd = (
                    f"scp -i {ssh_key} -o StrictHostKeyChecking=no "
                    f"{user}@{host}:{remote_csv_path} {local_csv_path}"
                )
                self.logger.info(f"Copying remote CSV to local dir: {scp_cmd}")
                scp_result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
                if scp_result.returncode != 0:
                    self.logger.error(f"SCP failed: {scp_result.stderr.strip()}")
                    raise Exception("Failed to copy remote CSV")

                if not os.path.exists(local_csv_path):
                    raise Exception("Remote monitor output file not found after SCP.")
           
            # ---- Parse results ----
            result = self.parse_test_results(
                result_file=local_csv_path,
                auth_method=auth_method,
                ue_count=ue_count,
                iteration=iteration,
                duration=test_duration
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
        """
        Parse results from a CSV written by the monitor.
        Supports either:
        (A) one-row summary CSV with columns like:
            ['timestamp','num_UEs','total_time_sec','avg_CPU_percent','avg_memory_MB']
        (B) multi-row sample CSV with columns like:
            ['timestamp','cpu_usage','memory_usage','processing_time'] (names may vary)
        Returns a unified dict for a single test iteration.
        """
        def pick(df, *aliases, agg="mean"):
            """Pick the first existing column among aliases (case-insensitive) and aggregate."""
            lower_map = {c.lower(): c for c in df.columns}
            for a in aliases:
                if a.lower() in lower_map:
                    col = lower_map[a.lower()]
                    series = df[col].dropna()
                    if series.empty:
                        return None
                    if agg == "mean":
                        return float(series.mean())
                    if agg == "max":
                        return float(series.max())
                    if agg == "last":
                        return float(series.iloc[-1])
                    return float(series.mean())
            return None

        # Default/fallback
        fallback = {
            'auth_method': auth_method,
            'ue_count': ue_count,
            'iteration': iteration,
            'test_duration': duration,
            'avg_processing_time': None,
            'max_cpu_usage': None,
            'avg_memory_usage': None,
            'timestamp': datetime.now().isoformat()
        }

        if not result_file or not os.path.exists(result_file):
            self.logger.warning(f"No result file to parse: {result_file}")
            return fallback

        try:
            df = pd.read_csv(result_file)
            if df.empty:
                self.logger.warning(f"Result CSV empty: {result_file}")
                return fallback

            # (A) One-row summary?
            cols_lower = [c.lower() for c in df.columns]
            is_summary_style = (len(df) == 1) and any(c in cols_lower for c in ['avg_cpu_percent', 'avg memory mb', 'avg_memory_mb'])

            if is_summary_style:
                avg_cpu = pick(df, 'avg_CPU_percent', 'cpu_usage', 'cpu_percent', agg="last")
                avg_mem = pick(df, 'avg_memory_MB', 'memory_usage', 'memory_mb', agg="last")
                return {
                    'auth_method': auth_method,
                    'ue_count': ue_count,
                    'iteration': iteration,
                    'test_duration': float(pick(df, 'total_time_sec', agg="last") or duration),
                    'avg_processing_time': None,
                    'max_cpu_usage': avg_cpu,
                    'avg_memory_usage': avg_mem,
                    'timestamp': str(df.iloc[-1].get('timestamp', datetime.now().isoformat()))
                }

            # (B) Multi-row samples: aggregate
            avg_proc = pick(df, 'processing_time', 'latency', 'avg_latency', agg="mean")
            max_cpu  = pick(df, 'cpu_usage', 'cpu_percent', 'avg_CPU_percent', agg="max")
            avg_mem  = pick(df, 'memory_usage', 'memory_mb', 'avg_memory_mb', agg="mean")

            return {
                'auth_method': auth_method,
                'ue_count': ue_count,
                'iteration': iteration,
                'test_duration': duration,
                'avg_processing_time': avg_proc,
                'max_cpu_usage': max_cpu,
                'avg_memory_usage': avg_mem,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to parse results from {result_file}: {e}")
            return fallback

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
        summary_stats = df.groupby(['auth_method', 'ue_count']).agg({
            'avg_processing_time': ['mean', 'std'],
            'max_cpu_usage': ['mean', 'std'],
            'avg_memory_usage': ['mean', 'std']
        }).round(4)
        summary_stats.to_csv(os.path.join(self.results_dir, "summary_statistics.csv"))

        if self.config['output']['generate_plots']:
            try:
                self.generate_plots(df)
            except Exception as e:
                self.logger.error(f"Failed to generate plots: {e}")

        self.logger.info(f"Summary report generated in {self.results_dir}")

    def generate_plots(self, df):
        """Generate performance comparison plots"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))

        metrics = [('avg_processing_time', 'Average Processing Time (s)'),
                   ('max_cpu_usage', 'Maximum CPU Usage (%)'),
                   ('avg_memory_usage', 'Average Memory Usage (MB)'),
                   ('test_duration', 'Test Duration (s)')]

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
        """Parse a CSV that lives on the remote core (read via SSH)."""
        fallback = {
            'auth_method': auth_method, 'ue_count': ue_count, 'iteration': iteration,
            'test_duration': duration, 'avg_processing_time': None,
            'max_cpu_usage': None, 'avg_memory_usage': None,
            'timestamp': datetime.now().isoformat()
        }
        text = self._read_remote_text(remote_csv_path)
        if not text: return fallback

        try:
            df = pd.read_csv(io.StringIO(text))
            if df.empty: return fallback

            def pick(df, *aliases, agg="mean"):
                lower = {c.lower(): c for c in df.columns}
                for a in aliases:
                    if a.lower() in lower:
                        s = df[lower[a.lower()]].dropna()
                        if s.empty: return None
                        return float(s.mean() if agg=="mean" else s.max() if agg=="max" else s.iloc[-1])
                return None

            cols = [c.lower() for c in df.columns]
            is_summary = (len(df)==1) and any(c in cols for c in ['avg_cpu_percent','avg memory mb','avg_memory_mb'])

            if is_summary:
                return {
                    'auth_method': auth_method, 'ue_count': ue_count, 'iteration': iteration,
                    'test_duration': float(pick(df,'total_time_sec',agg="last") or duration),
                    'avg_processing_time': None,
                    'max_cpu_usage': pick(df,'avg_CPU_percent','cpu_usage','cpu_percent',agg="last"),
                    'avg_memory_usage': pick(df,'avg_memory_MB','memory_usage','memory_mb',agg="last"),
                    'timestamp': str(df.iloc[-1].get('timestamp', datetime.now().isoformat()))
                }

            return {
                'auth_method': auth_method, 'ue_count': ue_count, 'iteration': iteration,
                'test_duration': duration,
                'avg_processing_time': pick(df,'processing_time','latency','avg_latency',agg="mean"),
                'max_cpu_usage': pick(df,'cpu_usage','cpu_percent','avg_CPU_percent',agg="max"),
                'avg_memory_usage': pick(df,'memory_usage','memory_mb','avg_memory_mb',agg="mean"),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to parse remote CSV {remote_csv_path}: {e}")
            return fallback

def main():
    parser = argparse.ArgumentParser(description='5G Authentication Performance Test Orchestrator')
    parser.add_argument('--config', '-c', type=str, default=None, help='Path to YAML configuration file (optional)')
    parser.add_argument('--auth-methods', type=str, nargs='+', help='Authentication methods to test (overrides config)')
    parser.add_argument('--ue-counts', type=int, nargs='+', help='UE counts to test (overrides config)')
    parser.add_argument('--iterations', type=int, help='Number of iterations per test (overrides config)')
    args = parser.parse_args()

    orchestrator = TestOrchestrator(config_file=args.config)
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
