import time
import random
import math
import json
from multiprocessing import Pool, Process, Queue, cpu_count
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Tuple
from dataclasses import dataclass


def generate_data(n: int) -> List[int]:
    return [random.randint(1, 1000) for _ in range(n)]


def process_number(number: int) -> Tuple[int, int]:

    return number, math.factorial(number)


def single_thread_processing(data: List[int]) -> List[Tuple[int, int]]:
    return [process_number(num) for num in data]


def thread_pool_processing(data: List[int], max_workers: int = None) -> List[Tuple[int, int]]:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_number, data))
    return results


def process_pool_processing(data: List[int], num_processes: int = None) -> List[Tuple[int, int]]:
    if num_processes is None:
        num_processes = cpu_count()

    with Pool(processes=num_processes) as pool:
        results = pool.map(process_number, data)

    return results


def worker_process(input_queue: Queue, output_queue: Queue):
    while True:
        item = input_queue.get()

        if item is None:
            break

        result = process_number(item)
        output_queue.put(result)


def manual_process_processing(data: List[int], num_processes: int = None) -> List[Tuple[int, int]]:
    if num_processes is None:
        num_processes = cpu_count()

    input_queue = Queue()
    output_queue = Queue()

    for item in data:
        input_queue.put(item)

    for _ in range(num_processes):
        input_queue.put(None)

    processes = []
    for _ in range(num_processes):
        p = Process(target=worker_process, args=(input_queue, output_queue))
        p.start()
        processes.append(p)

    results = []
    for _ in range(len(data)):
        results.append(output_queue.get())

    for p in processes:
        p.join()

    return results


def concurrent_process_pool_processing(data: List[int], max_workers: int = None) -> List[Tuple[int, int]]:
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_number, data))
    return results


@dataclass
class BenchmarkResult:
    name: str
    time: float
    speedup: float = 1.0


def benchmark_methods(data: List[int]) -> List[BenchmarkResult]:
    results = []
    num_cpus = cpu_count()

    start = time.time()
    single_result = single_thread_processing(data)
    baseline_time = time.time() - start

    results.append(BenchmarkResult("Single Thread", baseline_time, 1.0))

    start = time.time()
    thread_pool_processing(data, max_workers=num_cpus)
    thread_time = time.time() - start

    results.append(BenchmarkResult("Thread Pool", thread_time, baseline_time / thread_time))

    start = time.time()
    process_pool_processing(data, num_processes=num_cpus)
    pool_time = time.time() - start

    results.append(BenchmarkResult("Process Pool", pool_time, baseline_time / pool_time))

    start = time.time()
    manual_process_processing(data, num_processes=num_cpus)
    manual_time = time.time() - start

    results.append(BenchmarkResult("Manual Processes", manual_time, baseline_time / manual_time))

    start = time.time()
    concurrent_process_pool_processing(data, max_workers=num_cpus)
    concurrent_time = time.time() - start

    results.append(BenchmarkResult("ProcessPoolExecutor", concurrent_time, baseline_time / concurrent_time))

    return results, single_result


def print_results_table(results: List[BenchmarkResult]):
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ СРАВНЕНИЯ ПРОИЗВОДИТЕЛЬНОСТИ")
    print("=" * 70)
    print(f"{'Метод':<30} {'Время (сек)':<15} {'Ускорение':<15}")
    print("-" * 70)

    for result in results:
        print(f"{result.name:<30} {result.time:<15.2f} {result.speedup:<15.2f}x")

    print("=" * 70)


def save_results_to_json(results: List[BenchmarkResult],
                         processed_data: List[Tuple[int, int]],
                         filename: str = "benchmark_results.json"):
    output = {
        "benchmark_results": [
            {
                "method": r.name,
                "time_seconds": r.time,
                "speedup": r.speedup
            }
            for r in results
        ],
        "processed_data_sample": processed_data,
        "total_records": len(processed_data)
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def main():
    DATA_SIZE = 100000
    data = generate_data(DATA_SIZE)

    benchmark_results, processed_data = benchmark_methods(data)
    save_results_to_json(benchmark_results, processed_data)
    print_results_table(benchmark_results)


if __name__ == "__main__":
    main()
