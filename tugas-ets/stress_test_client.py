import socket
import json
import base64
import logging
import os
import time
import statistics
import csv
import concurrent.futures
from collections import defaultdict

logger = logging.getLogger(__name__)

class StressTestClient:
    def __init__(self, server_address=('localhost', 6666)):
        self.server_address = server_address
        self.results = {'upload': [], 'download': [], 'list': []}
        self.success_count = {'upload': 0, 'download': 0, 'list': 0}
        self.fail_count = {'upload': 0, 'download': 0, 'list': 0}
        
        if not os.path.exists('files'):
            os.makedirs('files')
        
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

    def generate_test_file(self, size_mb):
        filename = f"file_{size_mb}MB.bin"
        filepath = os.path.join('files', filename)
        
        if os.path.exists(filepath) and os.path.getsize(filepath) == size_mb * 1024 * 1024:
            logger.info(f"Test file {filename} already exists with correct size")
            return filepath
        
        logger.info(f"Generating test file: {filename} ({size_mb} MB)")
        with open(filepath, 'wb') as f:
            chunk_size = 1024 * 1024
            for _ in range(size_mb):
                f.write(os.urandom(chunk_size))
        
        logger.info(f"Test file generated: {filepath}")
        return filepath

    def send_command(self, command_str=""):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(600) # 10 menit timeout
        try:
            start_connect = time.time()
            sock.connect(self.server_address)
            connect_time = time.time() - start_connect
            logger.debug(f"Connection established to {self.server_address} in {connect_time:.2f}s")
            
            chunks = [command_str[i:i+65536] for i in range(0, len(command_str), 65536)]
            for chunk in chunks:
                sock.sendall((chunk).encode())
            
            sock.sendall("\r\n\r\n".encode())
            
            data_received = "" 
            while True:
                try:
                    data = sock.recv(1024*1024) 
                    if data:
                        data_received += data.decode()
                        if "\r\n\r\n" in data_received:
                            break
                    else:
                        logger.warning("Connection closed by server prematurely.")
                        break 
                except socket.timeout:
                    logger.error("Socket timeout while receiving data")
                    return {'status': 'ERROR', 'data': 'Socket timeout while receiving data'}
                except UnicodeDecodeError as e:
                    logger.error(f"Unicode decode error: {e}. Received data (partial): {data_received[-100:]}")
                    return {'status': 'ERROR', 'data': f'Unicode decode error: {e}'}

            
            json_response_part = data_received.split("\r\n\r\n", 1)[0]
            
            try:
                hasil = json.loads(json_response_part)
                return hasil
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}. Raw response part: {json_response_part[:500]}") # Log sebagian kecil respons
                return {'status': 'ERROR', 'data': f'JSON decode error: {e}'}

        except socket.timeout as e:
            logger.error(f"Socket timeout: {str(e)}")
            return {'status': 'ERROR', 'data': f'Socket timeout: {str(e)}'}
        except ConnectionRefusedError:
            logger.error(f"Connection refused to {self.server_address}. Is the server running?")
            return {'status': 'ERROR', 'data': 'Connection refused. Is the server running?'}
        except Exception as e:
            logger.error(f"Error in send_command: {str(e)}")
            return {'status': 'ERROR', 'data': str(e)}
        finally:
            sock.close()

    def perform_upload(self, file_path, worker_id):
        start_time = time.time()
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        try:
            logger.info(f"Worker {worker_id}: Starting upload of {filename} ({file_size/1024/1024:.2f} MB)")
            
            with open(file_path, 'rb') as fp:
                file_content_bytes = fp.read()
            file_content_b64 = base64.b64encode(file_content_bytes).decode('ascii')
            
            command_str = f"UPLOAD {filename} {file_content_b64}"
            
            result = self.send_command(command_str)
            
            end_time = time.time()
            duration = end_time - start_time
            throughput = file_size / duration if duration > 0 else 0
            
            if result.get('status') == 'OK':
                logger.info(f"Worker {worker_id}: Upload successful - {filename} ({file_size/1024/1024:.2f} MB) in {duration:.2f}s - {throughput/1024/1024:.2f} MB/s")
                self.success_count['upload'] += 1
                status_to_return = 'OK'
            else:
                logger.error(f"Worker {worker_id}: Upload failed - {filename}: {result.get('data', 'No error message')}")
                self.fail_count['upload'] += 1
                status_to_return = 'ERROR'
                
            return {
                'worker_id': worker_id, 'operation': 'upload', 'file_size': file_size, 'duration': duration, 
                'throughput': throughput, 'status': status_to_return, 'server_message': result.get('data')
            }
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"Worker {worker_id}: Upload exception - {filename}: {str(e)}", exc_info=True)
            self.fail_count['upload'] += 1
            return {
                'worker_id': worker_id, 'operation': 'upload', 'file_size': file_size, 'duration': duration, 
                'throughput': 0, 'status': 'ERROR', 'error': str(e)
            }

    def perform_download(self, filename, worker_id):
        start_time = time.time()
        
        try:
            logger.info(f"Worker {worker_id}: Starting download of {filename}")
            
            command_str = f"GET {filename}"
            result = self.send_command(command_str)
            
            if result.get('status') == 'OK' and 'data_file' in result:
                try:
                    file_content_b64 = result['data_file']
                    file_content_bytes = base64.b64decode(file_content_b64)
                except Exception as e:
                    logger.error(f"Worker {worker_id}: Error decoding/processing downloaded file content for {filename}: {e}")
                    self.fail_count['download'] += 1
                    return {
                        'worker_id': worker_id, 'operation': 'download', 'file_size': 0,
                        'duration': time.time() - start_time, 'throughput': 0, 'status': 'ERROR',
                        'error': f'Content processing error: {e}'
                    }

                file_size = len(file_content_bytes)
                
                download_path = os.path.join('downloads', f"worker{worker_id}_{filename}")
                with open(download_path, 'wb') as f:
                    f.write(file_content_bytes)
                
                end_time = time.time()
                duration = end_time - start_time
                throughput = file_size / duration if duration > 0 else 0
                
                logger.info(f"Worker {worker_id}: Download successful - {filename} ({file_size/1024/1024:.2f} MB) in {duration:.2f}s - {throughput/1024/1024:.2f} MB/s")
                self.success_count['download'] += 1
                status_to_return = 'OK'
                
                return {
                    'worker_id': worker_id, 'operation': 'download', 'file_size': file_size,
                    'duration': duration, 'throughput': throughput, 'status': status_to_return,
                    'server_message': result.get('data')
                }
            else:
                end_time = time.time()
                duration = end_time - start_time
                logger.error(f"Worker {worker_id}: Download failed - {filename}: {result.get('data', 'No error message')}")
                self.fail_count['download'] += 1
                
                return {
                    'worker_id': worker_id, 'operation': 'download', 'file_size': 0,
                    'duration': duration, 'throughput': 0, 'status': 'ERROR',
                    'error': result.get('data', 'Download failed without specific error')
                }
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"Worker {worker_id}: Download exception - {filename}: {str(e)}", exc_info=True)
            self.fail_count['download'] += 1
            
            return {
                'worker_id': worker_id, 'operation': 'download', 'file_size': 0,
                'duration': duration, 'throughput': 0, 'status': 'ERROR', 'error': str(e)
            }

    def perform_list(self, worker_id):
        start_time = time.time()
        
        try:
            command_str = "LIST"
            result = self.send_command(command_str)
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result.get('status') == 'OK' and 'data' in result:
                file_count = len(result['data'])
                logger.info(f"Worker {worker_id}: List successful - {file_count} files in {duration:.2f}s")
                self.success_count['list'] += 1
                status_to_return = 'OK'
            else:
                logger.error(f"Worker {worker_id}: List failed: {result.get('data', 'No error message')}")
                self.fail_count['list'] += 1
                status_to_return = 'ERROR'
                
            return {
                'worker_id': worker_id, 'operation': 'list', 'duration': duration,
                'status': status_to_return, 'server_message': result.get('data')
            }
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"Worker {worker_id}: List exception: {str(e)}", exc_info=True)
            self.fail_count['list'] += 1
            
            return {
                'worker_id': worker_id, 'operation': 'list', 'duration': duration,
                'status': 'ERROR', 'error': str(e)
            }

    def reset_counters(self):
        self.success_count = defaultdict(int)
        self.fail_count = defaultdict(int)
        self.results = defaultdict(list)

    def run_stress_test(self, operation, file_size_mb, client_pool_size, executor_type='thread'):
        self.reset_counters()
        
        if operation not in ['upload', 'download', 'list']:
            logger.error(f"Invalid operation: {operation}")
            return
            
        logger.info(f"Starting {operation} stress test with {file_size_mb}MB files, {client_pool_size} {executor_type} workers")
        
        test_file = None
        if operation == 'upload' or (operation == 'download' and file_size_mb > 0):
            test_file = self.generate_test_file(file_size_mb)
        
        if operation == 'download':
            if not test_file:
                logger.error("For download operation, a file_size_mb > 0 must be specified to generate/upload the test file first.")
                return None
            
            logger.info(f"Ensuring test file '{os.path.basename(test_file)}' exists on server for download test")
            upload_result = self.perform_upload(test_file, "setup_worker") 
            if upload_result['status'] != 'OK':
                logger.error(f"Failed to upload test file to server for download test: {upload_result.get('error', 'Unknown error')}")
                return None
            self.reset_counters()

        if executor_type == 'thread':
            executor_class = concurrent.futures.ThreadPoolExecutor
        elif executor_type == 'process':
            executor_class = concurrent.futures.ProcessPoolExecutor
        else:
            logger.error(f"Invalid executor type: {executor_type}. Defaulting to 'thread'.")
            executor_class = concurrent.futures.ThreadPoolExecutor
        
        all_results_for_current_test = []
        
        with executor_class(max_workers=client_pool_size) as executor:
            futures = []
            
            for i in range(client_pool_size):
                if operation == 'upload':
                    if not test_file:
                        logger.error("Test file not available for upload operation.")
                        continue
                    futures.append(executor.submit(self.perform_upload, test_file, i))
                elif operation == 'download':
                    if not test_file:
                        logger.error("Test file not available on server for download operation.")
                        continue
                    file_name_to_download = os.path.basename(test_file)
                    futures.append(executor.submit(self.perform_download, file_name_to_download, i))
                elif operation == 'list':
                    futures.append(executor.submit(self.perform_list, i))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        all_results_for_current_test.append(result)
                except Exception as e:
                    logger.error(f"Worker task failed with exception: {str(e)}", exc_info=True)

        successful_ops = [r for r in all_results_for_current_test if r and r.get('status') == 'OK']
        durations = [r['duration'] for r in successful_ops if 'duration' in r]
        throughputs = [r['throughput'] for r in successful_ops if r.get('throughput', 0) > 0 and 'throughput' in r]
        
        current_success_count = self.success_count[operation]
        current_fail_count = self.fail_count[operation]
        total_ops = current_success_count + current_fail_count

        if not successful_ops:
            logger.warning(f"No successful {operation} operations to calculate statistics for this run.")
            return {
                'operation': operation,
                'file_size_mb': file_size_mb if operation != 'list' else 'N/A',
                'client_pool_size': client_pool_size,
                'executor_type': executor_type,
                'avg_duration': 0, 'median_duration': 0, 'min_duration': 0, 'max_duration': 0,
                'avg_throughput': 0, 'median_throughput': 0, 'min_throughput': 0, 'max_throughput': 0,
                'success_count': current_success_count,
                'fail_count': current_fail_count,
                'total_ops': total_ops
            }
        
        stats = {
            'operation': operation,
            'file_size_mb': file_size_mb if operation != 'list' else 'N/A',
            'client_pool_size': client_pool_size,
            'executor_type': executor_type,
            'avg_duration': statistics.mean(durations) if durations else 0,
            'median_duration': statistics.median(durations) if durations else 0,
            'min_duration': min(durations) if durations else 0,
            'max_duration': max(durations) if durations else 0,
            'avg_throughput': statistics.mean(throughputs) if throughputs else 0,
            'median_throughput': statistics.median(throughputs) if throughputs else 0,
            'min_throughput': min(throughputs) if throughputs else 0,
            'max_throughput': max(throughputs) if throughputs else 0,
            'success_count': current_success_count,
            'fail_count': current_fail_count,
            'total_ops': total_ops
        }
        
        logger.info(f"Test complete for this configuration: {stats['success_count']} succeeded, {stats['fail_count']} failed from {stats['total_ops']} total attempts.")
        if durations:
             logger.info(f"Average duration: {stats['avg_duration']:.2f}s")
        if throughputs:
            logger.info(f"Average throughput: {stats['avg_throughput']/1024/1024:.2f} MB/s")
        
        return stats

    def save_results_to_csv(self, all_stats_list, filename_prefix="stress_test_results"):
        if not all_stats_list:
            logger.info("No statistics to save.")
            return None

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        csv_filename = f"{filename_prefix}_{timestamp}.csv"
        
        fieldnames = list(all_stats_list[0].keys())
        if 'total_ops' not in fieldnames:
             fieldnames.append('total_ops')
        if 'server_pool_size' not in fieldnames:
            fieldnames.insert(fieldnames.index('client_pool_size') + 1, 'server_pool_size')

        with open(csv_filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for stats_row in all_stats_list:
                writer.writerow(stats_row)
        
        logger.info(f"Results saved to {csv_filename}")
        return csv_filename