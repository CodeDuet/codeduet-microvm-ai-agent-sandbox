#!/usr/bin/env python3
"""Load testing script for MicroVM Sandbox API."""

import asyncio
import aiohttp
import time
import statistics
import argparse
import json
import sys
from typing import List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


@dataclass
class TestResult:
    """Result of a single test operation."""
    operation: str
    duration: float
    success: bool
    error: str = ""


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    base_url: str = "http://localhost:8000"
    concurrent_users: int = 10
    operations_per_user: int = 5
    vm_template: str = "linux-default"
    auth_token: str = ""
    timeout: int = 30


class LoadTester:
    """Load testing framework for MicroVM API."""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[TestResult] = []
        self.session: aiohttp.ClientSession = None

    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        headers = {}
        
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def create_vm(self, vm_name: str) -> TestResult:
        """Test VM creation."""
        vm_data = {
            "name": vm_name,
            "os_type": "linux",
            "vcpus": 1,
            "memory_mb": 256,
            "template": self.config.vm_template
        }
        
        start_time = time.time()
        try:
            async with self.session.post(
                f"{self.config.base_url}/api/v1/vms",
                json=vm_data
            ) as response:
                duration = time.time() - start_time
                success = response.status == 201
                error = "" if success else f"Status: {response.status}"
                
                return TestResult("create_vm", duration, success, error)
        except Exception as e:
            duration = time.time() - start_time
            return TestResult("create_vm", duration, False, str(e))

    async def start_vm(self, vm_name: str) -> TestResult:
        """Test VM startup."""
        start_time = time.time()
        try:
            async with self.session.post(
                f"{self.config.base_url}/api/v1/vms/{vm_name}/start"
            ) as response:
                duration = time.time() - start_time
                success = response.status == 200
                error = "" if success else f"Status: {response.status}"
                
                return TestResult("start_vm", duration, success, error)
        except Exception as e:
            duration = time.time() - start_time
            return TestResult("start_vm", duration, False, str(e))

    async def get_vm_info(self, vm_name: str) -> TestResult:
        """Test VM info retrieval."""
        start_time = time.time()
        try:
            async with self.session.get(
                f"{self.config.base_url}/api/v1/vms/{vm_name}"
            ) as response:
                duration = time.time() - start_time
                success = response.status == 200
                error = "" if success else f"Status: {response.status}"
                
                return TestResult("get_vm_info", duration, success, error)
        except Exception as e:
            duration = time.time() - start_time
            return TestResult("get_vm_info", duration, False, str(e))

    async def list_vms(self) -> TestResult:
        """Test VM listing."""
        start_time = time.time()
        try:
            async with self.session.get(
                f"{self.config.base_url}/api/v1/vms"
            ) as response:
                duration = time.time() - start_time
                success = response.status == 200
                error = "" if success else f"Status: {response.status}"
                
                return TestResult("list_vms", duration, success, error)
        except Exception as e:
            duration = time.time() - start_time
            return TestResult("list_vms", duration, False, str(e))

    async def execute_command(self, vm_name: str) -> TestResult:
        """Test command execution."""
        command_data = {
            "command": "echo 'load test command'"
        }
        
        start_time = time.time()
        try:
            async with self.session.post(
                f"{self.config.base_url}/api/v1/vms/{vm_name}/execute",
                json=command_data
            ) as response:
                duration = time.time() - start_time
                success = response.status == 200
                error = "" if success else f"Status: {response.status}"
                
                return TestResult("execute_command", duration, success, error)
        except Exception as e:
            duration = time.time() - start_time
            return TestResult("execute_command", duration, False, str(e))

    async def stop_vm(self, vm_name: str) -> TestResult:
        """Test VM stopping."""
        start_time = time.time()
        try:
            async with self.session.post(
                f"{self.config.base_url}/api/v1/vms/{vm_name}/stop"
            ) as response:
                duration = time.time() - start_time
                success = response.status == 200
                error = "" if success else f"Status: {response.status}"
                
                return TestResult("stop_vm", duration, success, error)
        except Exception as e:
            duration = time.time() - start_time
            return TestResult("stop_vm", duration, False, str(e))

    async def delete_vm(self, vm_name: str) -> TestResult:
        """Test VM deletion."""
        start_time = time.time()
        try:
            async with self.session.delete(
                f"{self.config.base_url}/api/v1/vms/{vm_name}"
            ) as response:
                duration = time.time() - start_time
                success = response.status == 204
                error = "" if success else f"Status: {response.status}"
                
                return TestResult("delete_vm", duration, success, error)
        except Exception as e:
            duration = time.time() - start_time
            return TestResult("delete_vm", duration, False, str(e))

    async def user_workflow(self, user_id: int) -> List[TestResult]:
        """Simulate a complete user workflow."""
        results = []
        
        for operation_id in range(self.config.operations_per_user):
            vm_name = f"load-test-user{user_id}-op{operation_id}"
            
            # Complete VM lifecycle
            results.append(await self.create_vm(vm_name))
            results.append(await self.start_vm(vm_name))
            
            # Wait a bit for VM to be ready
            await asyncio.sleep(2)
            
            results.append(await self.get_vm_info(vm_name))
            results.append(await self.execute_command(vm_name))
            results.append(await self.list_vms())
            results.append(await self.stop_vm(vm_name))
            results.append(await self.delete_vm(vm_name))
            
            # Small delay between operations
            await asyncio.sleep(0.5)
        
        return results

    async def run_load_test(self) -> Dict[str, Any]:
        """Run the complete load test."""
        print(f"Starting load test with {self.config.concurrent_users} concurrent users")
        print(f"Each user will perform {self.config.operations_per_user} operations")
        
        start_time = time.time()
        
        # Run concurrent user workflows
        user_tasks = [
            self.user_workflow(user_id) 
            for user_id in range(self.config.concurrent_users)
        ]
        
        user_results = await asyncio.gather(*user_tasks, return_exceptions=True)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Flatten results
        all_results = []
        for user_result in user_results:
            if isinstance(user_result, list):
                all_results.extend(user_result)
            else:
                print(f"User workflow failed: {user_result}")
        
        self.results = all_results
        
        return {
            "total_duration": total_duration,
            "total_operations": len(all_results),
            "operations_per_second": len(all_results) / total_duration if total_duration > 0 else 0
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        if not self.results:
            return {"error": "No test results available"}
        
        # Group results by operation type
        operations = {}
        for result in self.results:
            if result.operation not in operations:
                operations[result.operation] = []
            operations[result.operation].append(result)
        
        # Calculate statistics for each operation
        operation_stats = {}
        for op_name, op_results in operations.items():
            durations = [r.duration for r in op_results]
            success_count = sum(1 for r in op_results if r.success)
            
            operation_stats[op_name] = {
                "total_requests": len(op_results),
                "successful_requests": success_count,
                "failed_requests": len(op_results) - success_count,
                "success_rate": success_count / len(op_results) * 100,
                "avg_duration": statistics.mean(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "p95_duration": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
                "p99_duration": statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else max(durations)
            }
        
        # Overall statistics
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        all_durations = [r.duration for r in self.results]
        
        overall_stats = {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": total_requests - successful_requests,
            "overall_success_rate": successful_requests / total_requests * 100,
            "avg_response_time": statistics.mean(all_durations),
            "min_response_time": min(all_durations),
            "max_response_time": max(all_durations),
            "p95_response_time": statistics.quantiles(all_durations, n=20)[18] if len(all_durations) >= 20 else max(all_durations),
            "p99_response_time": statistics.quantiles(all_durations, n=100)[98] if len(all_durations) >= 100 else max(all_durations)
        }
        
        # Error analysis
        errors = {}
        for result in self.results:
            if not result.success and result.error:
                if result.error not in errors:
                    errors[result.error] = 0
                errors[result.error] += 1
        
        return {
            "overall": overall_stats,
            "by_operation": operation_stats,
            "errors": errors,
            "test_config": {
                "concurrent_users": self.config.concurrent_users,
                "operations_per_user": self.config.operations_per_user,
                "base_url": self.config.base_url
            }
        }


async def main():
    """Main function for load testing."""
    parser = argparse.ArgumentParser(description="MicroVM Sandbox Load Testing")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for API")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--operations", type=int, default=5, help="Operations per user")
    parser.add_argument("--template", default="linux-default", help="VM template to use")
    parser.add_argument("--token", default="", help="Authentication token")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--output", help="Output file for results (JSON)")
    
    args = parser.parse_args()
    
    config = LoadTestConfig(
        base_url=args.url,
        concurrent_users=args.users,
        operations_per_user=args.operations,
        vm_template=args.template,
        auth_token=args.token,
        timeout=args.timeout
    )
    
    try:
        async with LoadTester(config) as tester:
            # Run the load test
            test_summary = await tester.run_load_test()
            
            # Generate detailed report
            report = tester.generate_report()
            
            # Print summary
            print(f"\n{'='*60}")
            print("LOAD TEST SUMMARY")
            print(f"{'='*60}")
            print(f"Total Duration: {test_summary['total_duration']:.2f}s")
            print(f"Total Operations: {test_summary['total_operations']}")
            print(f"Operations/Second: {test_summary['operations_per_second']:.2f}")
            print(f"Overall Success Rate: {report['overall']['overall_success_rate']:.1f}%")
            print(f"Average Response Time: {report['overall']['avg_response_time']*1000:.1f}ms")
            print(f"95th Percentile: {report['overall']['p95_response_time']*1000:.1f}ms")
            print(f"99th Percentile: {report['overall']['p99_response_time']*1000:.1f}ms")
            
            print(f"\n{'='*60}")
            print("OPERATION BREAKDOWN")
            print(f"{'='*60}")
            
            for op_name, stats in report["by_operation"].items():
                print(f"\n{op_name.upper()}:")
                print(f"  Requests: {stats['total_requests']}")
                print(f"  Success Rate: {stats['success_rate']:.1f}%")
                print(f"  Avg Time: {stats['avg_duration']*1000:.1f}ms")
                print(f"  95th Percentile: {stats['p95_duration']*1000:.1f}ms")
            
            if report["errors"]:
                print(f"\n{'='*60}")
                print("ERRORS")
                print(f"{'='*60}")
                for error, count in report["errors"].items():
                    print(f"  {error}: {count} occurrences")
            
            # Save to file if requested
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(report, f, indent=2)
                print(f"\nDetailed results saved to {args.output}")
            
            # Exit with appropriate code
            success_rate = report['overall']['overall_success_rate']
            if success_rate < 95.0:
                print(f"\nWARNING: Success rate {success_rate:.1f}% below 95% threshold")
                sys.exit(1)
            else:
                print(f"\nLOAD TEST PASSED: Success rate {success_rate:.1f}%")
                sys.exit(0)
                
    except Exception as e:
        print(f"Load test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())