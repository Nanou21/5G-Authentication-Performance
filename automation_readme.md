# 5G Authentication Performance Test Automation

This repository provides automated testing tools for comparing the performance of 5G-AKA and EAP-AKA' authentication methods in 5G networks. The automation suite includes Python-based orchestration with configuration management and comprehensive result analysis.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Python Orchestrator](#python-orchestrator)
- [Configuration Management](#configuration-management)
- [Understanding Results](#understanding-results)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## 🔧 Prerequisites

### System Requirements
- Ubuntu 18.04+ or similar Linux distribution
- Python 3.7+
- Open5GS (5G Core Network)
- UERANSIM (UE and RAN Simulator)
- sudo privileges for service management

### Network Setup
- Two VMs configured on network `192.168.0.xx`
- Open5GS properly configured and tested
- UERANSIM properly configured and tested
- All original test scripts from the base repository

### Python Dependencies
```bash
pip install pandas matplotlib pyyaml psutil
```

### Required Files
Ensure these files are in your working directory:
- `change_authmethod.py`
- `startservices.sh`
- `add_subscribers.py`
- `start_gnb.sh`
- `launch_ues.sh`
- `Memoryusage.py`

## 🚀 Quick Start

### 1. Basic Automated Testing (Default Configuration)
```bash
# Run with built-in defaults - no configuration file needed
python3 automated_test_orchestrator.py
```

### 2. Using YAML Configuration
```bash
# Run with YAML configuration file
python3 automated_test_orchestrator.py --config test_config.yaml
```

### 3. Command Line Overrides
```bash
# Override specific settings via command line
python3 automated_test_orchestrator.py --config test_config.yaml --auth-methods 5G_AKA --iterations 5

# Use only command line arguments (no YAML file)
python3 automated_test_orchestrator.py --auth-methods 5G_AKA EAP_AKA --ue-counts 10 50 100 --iterations 3
```

**Default Test Parameters (if no configuration provided):**
- Authentication methods: 5G_AKA, EAP_AKA
- UE counts: 10, 25, 50, 75, 100
- 3 iterations per test configuration

### 2. Check Results
Results are automatically saved in a timestamped directory:
```bash
ls automated_test_results_YYYYMMDD_HHMMSS/
```

## 🐍 Python Orchestrator

### Core Features

The Python orchestrator (`automated_test_orchestrator.py`) provides:

- **YAML Configuration Support** - Use configuration files or built-in defaults
- **Command Line Interface** - Override settings via command line arguments
- **Automated test execution** across multiple configurations
- **Intelligent process management** with cleanup
- **Real-time logging** and progress tracking
- **Result consolidation** and analysis
- **Performance visualization** generation
- **Error handling** and recovery

### Configuration Options

The orchestrator supports three ways to configure tests:

#### 1. YAML Configuration File (Recommended)
```bash
python3 automated_test_orchestrator.py --config test_config.yaml
```

#### 2. Command Line Arguments
```bash
python3 automated_test_orchestrator.py --auth-methods 5G_AKA --ue-counts 10 25 50 --iterations 3
```

#### 3. Built-in Defaults
```bash
python3 automated_test_orchestrator.py  # Uses sensible defaults
```

#### Configuration Hierarchy
- Command line arguments override YAML settings
- YAML settings override built-in defaults
- Built-in defaults are used if no other configuration is provided

### Running with Custom Parameters

#### Option 1: YAML Configuration (Recommended)
Create a custom YAML file and run:
```bash
python3 automated_test_orchestrator.py --config my_custom_config.yaml
```

#### Option 2: Command Line Arguments
```bash
# Test only one authentication method
python3 automated_test_orchestrator.py --auth-methods 5G_AKA

# Test specific UE counts with more iterations
python3 automated_test_orchestrator.py --ue-counts 10 50 100 --iterations 5

# Combine YAML with command line overrides
python3 automated_test_orchestrator.py --config test_config.yaml --iterations 10
```

#### Option 3: Direct Code Modification (Legacy)
```python
# Edit the class initialization for permanent changes
orchestrator = TestOrchestrator()
# Configuration is now loaded from YAML or defaults automatically
```

### Command Line Arguments

```bash
python3 automated_test_orchestrator.py --help
```

Available arguments:
- `--config, -c`: Path to YAML configuration file
- `--auth-methods`: Authentication methods to test (space-separated)
- `--ue-counts`: UE counts to test (space-separated numbers)
- `--iterations`: Number of iterations per test configuration

### Output Structure

```
automated_test_results_20250818_143022/
├── test_orchestrator.log              # Main execution log
├── consolidated_results.json          # All results in JSON format
├── test_summary.csv                   # Summary statistics
├── summary_statistics.csv             # Grouped statistics
├── performance_comparison.png         # Visualization charts
├── 5G_AKA_10ues_iter1/                # Individual test results
│   ├── registration_overhead_summary.csv
│   └── performance_output.log
├── 5G_AKA_10ues_iter2/
│   └── ...
└── EAP_AKA_100ues_iter3/
    └── ...
```

## ⚙️ Configuration Management

### YAML Configuration File

The `test_config.yaml` provides a structured way to configure tests without modifying code. The Python orchestrator **automatically supports** YAML configuration.

#### Using YAML Configuration

```bash
# Use provided configuration file
python3 automated_test_orchestrator.py --config test_config.yaml

# Use custom configuration file
python3 automated_test_orchestrator.py --config my_test_setup.yaml
```

If no configuration file is specified, the orchestrator uses built-in defaults.

#### Creating Custom Configuration Files

Create your own YAML file based on `test_config.yaml`:

```yaml
# my_custom_config.yaml
test_configuration:
  authentication_methods: ["5G_AKA"]  # Test only one method
  ue_counts: [25, 50, 100]            # Skip small tests
  iterations_per_test: 5              # More iterations for accuracy

timing:
  test_duration_base: 120             # Longer base duration
  inter_test_wait: 60                 # More rest between tests

output:
  log_level: "DEBUG"                  # More detailed logging
  generate_plots: true                # Enable plot generation
```

#### Key Configuration Sections

##### Test Parameters
```yaml
test_configuration:
  authentication_methods:
    - "5G_AKA"
    - "EAP_AKA"
  ue_counts: [10, 25, 50, 75, 100]
  iterations_per_test: 3
```

##### Timing Configuration
```yaml
timing:
  service_restart_wait: 15    # Time to wait after restarting services
  gnb_startup_wait: 10        # Time to wait after starting gNodeB
  test_duration_base: 60      # Base test duration
  test_duration_per_ue: 0.5   # Additional time per UE
  inter_test_wait: 30         # Wait between tests
```

##### Script Paths
```yaml
scripts:
  change_auth: "python3 change_authmethod.py"
  start_services: "sudo bash startservices.sh"
  add_subscribers: "sudo python3 add_subscribers.py"
  # ... other script paths
```

##### Error Handling
```yaml
error_handling:
  max_retries: 2              # Retry failed tests
  timeout_seconds: 300        # Command timeout
  continue_on_failure: true   # Continue if a test fails
  cleanup_on_error: true      # Clean up on errors
```

### Using Configuration

The orchestrator automatically loads and applies YAML configuration:

```bash
# Default behavior - uses built-in configuration
python3 automated_test_orchestrator.py

# Load custom YAML configuration
python3 automated_test_orchestrator.py --config production_tests.yaml

# Mix YAML config with command line overrides
python3 automated_test_orchestrator.py --config test_config.yaml --iterations 10

# Environment-specific configurations
python3 automated_test_orchestrator.py --config configs/lab_environment.yaml
python3 automated_test_orchestrator.py --config configs/production_environment.yaml
```

### Configuration Validation

The orchestrator validates configuration and provides helpful error messages:

```bash
# If YAML file is not found or invalid
$ python3 automated_test_orchestrator.py --config missing_file.yaml
Error loading config file missing_file.yaml: [Errno 2] No such file or directory
Using default configuration instead
Loaded default configuration
```

## 📊 Understanding Results

### Raw Results
Each test produces a `registration_overhead_summary.csv` file containing:
- Processing times for each UE registration
- CPU usage measurements
- Memory usage measurements
- Timestamps

### Consolidated Results

#### JSON Format (`consolidated_results.json`)
```json
[
  {
    "auth_method": "5G_AKA",
    "ue_count": 10,
    "iteration": 1,
    "test_duration": 75.3,
    "avg_processing_time": 2.45,
    "max_cpu_usage": 85.2,
    "avg_memory_usage": 1024.5,
    "timestamp": "2025-08-18T14:30:22"
  }
]
```

#### Summary Statistics (`summary_statistics.csv`)
Groups results by authentication method and UE count, showing:
- Mean values across iterations
- Standard deviations
- Performance trends

### Visualizations

The generated `performance_comparison.png` includes:
1. **Processing Time Comparison** - Authentication latency vs UE count
2. **CPU Usage Comparison** - Resource utilization patterns
3. **Memory Usage Comparison** - Memory consumption trends
4. **Test Duration** - Total time per test configuration

## 🔧 Customization

### Adding New Metrics

Extend the `parse_test_results` method:

```python
def parse_test_results(self, result_file, auth_method, ue_count, iteration, duration):
    df = pd.read_csv(result_file)
    
    # Add custom metrics
    success_rate = (df['status'] == 'success').mean() if 'status' in df.columns else None
    avg_latency = df['latency'].mean() if 'latency' in df.columns else None
    
    return {
        # ... existing metrics
        'success_rate': success_rate,
        'avg_latency': avg_latency
    }
```

### Adding New Metrics

Extend the `parse_test_results` method to capture additional metrics from your CSV files:

```python
def parse_test_results(self, result_file, auth_method, ue_count, iteration, duration):
    df = pd.read_csv(result_file)
    
    # Add custom metrics based on your CSV structure
    success_rate = (df['status'] == 'success').mean() if 'status' in df.columns else None
    avg_latency = df['latency'].mean() if 'latency' in df.columns else None
    
    return {
        # ... existing metrics
        'success_rate': success_rate,
        'avg_latency': avg_latency
    }
```

### Custom Test Durations via YAML

Instead of modifying code, use YAML configuration:

```yaml
# In test_config.yaml
timing:
  test_duration_base: 120        # Base duration in seconds
  test_duration_per_ue: 1.0      # Additional time per UE
  
  # Or disable dynamic calculation
  custom_test_duration: true
  fixed_test_duration: 180       # Fixed 3 minutes per test
```

### Environment-Specific Script Paths

Configure different script paths for different environments:

```yaml
# development_config.yaml
scripts:
  change_auth: "python3 change_authmethod.py"
  start_services: "bash startservices.sh"  # No sudo needed in dev

# production_config.yaml  
scripts:
  change_auth: "/opt/5g-tools/change_authmethod.py"
  start_services: "sudo systemctl start open5gs-suite"  # Different command
```

### Adding Email Notifications

```python
import smtplib
from email.mime.text import MIMEText

def send_completion_email(self, results_dir):
    # Configure email settings
    smtp_server = "your-smtp-server.com"
    sender_email = "your-email@domain.com"
    password = "your-password"
    receiver_email = "admin@domain.com"
    
    # Create message
    message = MIMEText(f"5G test automation completed. Results in: {results_dir}")
    message["Subject"] = "5G Authentication Tests Complete"
    message["From"] = sender_email
    message["To"] = receiver_email
    
    # Send email
    with smtplib.SMTP(smtp_server, 587) as server:
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())
```

### Parallel Test Execution

For faster execution with multiple test environments:

```python
import concurrent.futures
import threading

def run_parallel_tests(self):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for auth_method in self.auth_methods:
            future = executor.submit(self.run_auth_method_tests, auth_method)
            futures.append(future)
        
        # Wait for completion
        concurrent.futures.wait(futures)
```

## 🐛 Troubleshooting

### Common Issues

#### Permission Errors
```bash
sudo chown -R $USER:$USER /path/to/test/directory
chmod +x *.sh
```

#### Port Conflicts
```bash
# Check for occupied ports
sudo netstat -tlnp | grep :3868
sudo netstat -tlnp | grep :5868

# Kill processes using ports
sudo fuser -k 3868/tcp
```

#### Service Startup Failures
```bash
# Check service status
sudo systemctl status open5gs-*

# View detailed logs
journalctl -u open5gs-amf -f
```

#### Memory Issues
```bash
# Monitor system resources
htop
free -h
df -h

# Increase swap if needed
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Debug Mode

Enable detailed logging:

```python
# In setup_logging method
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
)
```

### Manual Test Verification

Before running automation, verify manual execution:

```bash
# Test basic workflow manually
python3 change_authmethod.py 5G_AKA
sudo bash startservices.sh
sudo python3 add_subscribers.py 10
sudo bash start_gnb.sh &
sudo bash launch_ues.sh 10
# Check if registration_overhead_summary.csv is created
```

## 🚀 Advanced Usage

### Integration with CI/CD

Create a GitHub Actions workflow:

```yaml
name: 5G Authentication Performance Tests
on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2 AM
  workflow_dispatch:

jobs:
  performance-test:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v2
      - name: Run Performance Tests
        run: |
          python3 automated_test_orchestrator.py
          # Upload results to artifact storage
```

### Cloud Integration

Upload results to cloud storage:

```python
import boto3

def upload_to_s3(self, results_dir):
    s3 = boto3.client('s3')
    bucket_name = 'your-test-results-bucket'
    
    for root, dirs, files in os.walk(results_dir):
        for file in files:
            local_path = os.path.join(root, file)
            s3_path = f"5g-tests/{os.path.relpath(local_path, results_dir)}"
            s3.upload_file(local_path, bucket_name, s3_path)
```

### Performance Monitoring Integration

Integrate with Prometheus/Grafana:

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

def push_metrics_to_prometheus(self, test_result):
    registry = CollectorRegistry()
    
    processing_time_gauge = Gauge('auth_processing_time_seconds', 
                                 'Authentication processing time', 
                                 ['auth_method', 'ue_count'], 
                                 registry=registry)
    
    processing_time_gauge.labels(
        auth_method=test_result['auth_method'],
        ue_count=test_result['ue_count']
    ).set(test_result['avg_processing_time'])
    
    push_to_gateway('localhost:9091', job='5g_auth_tests', registry=registry)
```

### Scaling for Large Tests

For testing with thousands of UEs:

```python
def run_large_scale_test(self, ue_count):
    # Batch UE registration
    batch_size = 100
    batches = ue_count // batch_size
    
    for batch in range(batches):
        start_ue = batch * batch_size + 1
        end_ue = min((batch + 1) * batch_size, ue_count)
        
        self.run_command(f"sudo bash launch_ues_batch.sh {start_ue} {end_ue}")
        time.sleep(10)  # Stagger batch launches
```

## 📝 Example Workflows

### Daily Performance Monitoring
```bash
# Create daily monitoring configuration
cat > daily_monitor.yaml << EOF
test_configuration:
  authentication_methods: ["5G_AKA", "EAP_AKA"]
  ue_counts: [50, 100]  # Moderate load
  iterations_per_test: 1

timing:
  inter_test_wait: 60  # More time between tests

output:
  results_dir_prefix: "daily_monitor"
EOF

# Run daily monitoring
python3 automated_test_orchestrator.py --config daily_monitor.yaml
```

### Regression Testing
```bash
# Create regression test configuration
cat > regression_test.yaml << EOF
test_configuration:
  authentication_methods: ["5G_AKA"]  # Test specific method
  ue_counts: [10, 25, 50, 75, 100]
  iterations_per_test: 5  # More iterations for accuracy

output:
  results_dir_prefix: "regression_test"
  log_level: "DEBUG"
EOF

python3 automated_test_orchestrator.py --config regression_test.yaml
```

### Stress Testing
```bash
# Use command line for quick stress test setup
python3 automated_test_orchestrator.py \
    --ue-counts 100 200 500 1000 \
    --iterations 1 \
    --auth-methods 5G_AKA EAP_AKA
```

### Quick Single Test
```bash
# Test just one configuration quickly
python3 automated_test_orchestrator.py \
    --auth-methods 5G_AKA \
    --ue-counts 50 \
    --iterations 1
```

## 📞 Support and Contributing

For issues or questions:
1. Check the troubleshooting section
2. Review logs in the results directory
3. Ensure all prerequisites are properly configured
4. Test manual execution before automation

Contributions welcome! Please submit pull requests with:
- Clear description of changes
- Test results demonstrating functionality
- Updated documentation as needed