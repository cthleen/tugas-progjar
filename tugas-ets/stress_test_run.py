import argparse
import logging
import os
import time
import sys

from stress_test_client import StressTestClient

def setup_logging(debug_mode=False, log_file="stress_test.log"):
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

def run_all_tests_scenario(client, file_sizes, client_pool_sizes, server_pool_sizes, executor_types, operations):
    all_stats_collected = []
    for server_pool_size in server_pool_sizes:
        logging.info(f"--- Starting tests for server pool size: {server_pool_size} ---")
        logging.info("IMPORTANT: Please ensure the server is (re)started with the "
                     f"appropriate pool size ({server_pool_size}) before proceeding.")
        try:
            input("Press Enter when the server is ready, or Ctrl+C to abort...")
        except KeyboardInterrupt:
            logging.warning("Test run aborted by user.")
            return []
            
        for executor_type in executor_types:
            logging.info(f"--- Using client executor: {executor_type} ---")
            for operation in operations:
                current_file_sizes = file_sizes if operation in ['upload', 'download'] else [0]
                for file_size_mb in current_file_sizes:
                    for client_pool_size in client_pool_sizes:
                        logging.info(f"*** Running: op={operation}, file_mb={file_size_mb if operation != 'list' else 'N/A'}, "
                                     f"clients={client_pool_size}, server_pool={server_pool_size}, exec={executor_type} ***")
                        
                        stats = client.run_stress_test(operation, file_size_mb, client_pool_size, executor_type)
                        
                        if stats:
                            stats['server_pool_size'] = server_pool_size
                            all_stats_collected.append(stats)
                        else:
                            logging.warning(f"Skipped or failed test for op={operation}, file_mb={file_size_mb}, "
                                            f"clients={client_pool_size}")
                        time.sleep(1)
    return all_stats_collected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='File Server Stress Test Client')
    
    parser.add_argument('--host', default='localhost', help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=6666, help='Server port (default: 6666)')
    parser.add_argument('--operation', choices=['upload', 'download', 'list', 'all'], default='all', 
                        help='Operation to test (default: all)')
    parser.add_argument('--file-sizes', type=int, nargs='+', default=[10, 50, 100], 
                        help='File sizes in MB for upload/download (default: 10 50 100)')
    parser.add_argument('--client-pools', type=int, nargs='+', default=[1, 5, 50], 
                        help='Client worker pool sizes (default: 1 5 50)')
    parser.add_argument('--server-pools', type=int, nargs='+', default=[1, 5, 50], 
                        help='Server worker pool sizes to test against (default: 1 5 50)')
    parser.add_argument('--executor', choices=['thread', 'process', 'both'], default='thread', 
                        help='Client executor type (default: thread)')
    parser.add_argument('--log-file', default='stress_test.log', help='Log file name')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args() 
    
    setup_logging(args.debug, args.log_file) 
    
    logger = logging.getLogger() 
    logger.info("Stress Test Client starting with arguments: %s", args)

    file_sizes_to_test = args.file_sizes
    client_pool_sizes_to_test = args.client_pools
    server_pool_sizes_to_test = args.server_pools
    
    if args.executor == 'both':
        executor_types_to_test = ['thread', 'process']
    else:
        executor_types_to_test = [args.executor]
        
    if args.operation == 'all':
        operations_to_test = ['list', 'download', 'upload']
    else:
        operations_to_test = [args.operation]
    
    client = StressTestClient(server_address=(args.host, args.port))
    
    is_single_specific_run = (
        len(operations_to_test) == 1 and
        (operations_to_test[0] == 'list' or len(file_sizes_to_test) == 1) and
        len(client_pool_sizes_to_test) == 1 and
        len(server_pool_sizes_to_test) == 1 and
        len(executor_types_to_test) == 1
    )

    collected_stats = []

    if is_single_specific_run:
        operation = operations_to_test[0]
        file_size = file_sizes_to_test[0] if operation != 'list' else 0
        client_pool = client_pool_sizes_to_test[0]
        server_pool = server_pool_sizes_to_test[0]
        executor_type = executor_types_to_test[0]

        logger.info(f"Running a single specific test: "
                    f"op={operation}, file_mb={file_size if operation != 'list' else 'N/A'}, "
                    f"clients={client_pool}, server_pool_prompt={server_pool}, exec={executor_type}")
        
        if server_pool_sizes_to_test:
            logging.info(f"IMPORTANT: Please ensure the server is (re)started with the "
                         f"appropriate pool size ({server_pool}) before proceeding.")
            try:
                input("Press Enter when the server is ready, or Ctrl+C to abort...")
            except KeyboardInterrupt:
                logging.warning("Test run aborted by user.")
                sys.exit(0)

        stats = client.run_stress_test(operation, file_size, client_pool, executor_type)
        if stats:
            stats['server_pool_size'] = server_pool
            collected_stats.append(stats)
    else:
        logger.info("Running multiple test combinations (full suite or partial).")
        collected_stats = run_all_tests_scenario(
            client, 
            file_sizes_to_test, 
            client_pool_sizes_to_test, 
            server_pool_sizes_to_test,
            executor_types_to_test, 
            operations_to_test
        )

    if collected_stats:
        csv_file = client.save_results_to_csv(collected_stats)
        if csv_file:
            logger.info(f"All test results saved to {csv_file}")
        else:
            logger.warning("No statistics were collected to save.")
    else:
        logger.info("No tests were run or no statistics were generated.")
    
    logger.info("Stress Test Client finished.")