import sys
import random
import time
import multiprocessing as mp
from mvs import parsing, max_processor_load, is_valid, create_claster_raspr


# Процесс, аналогичный базовому алгоритму
def fork(processors, net_limit, loads, comms, best_dict, lock, pid):
    """
    Процесс.
    - best_dict: {'value': int, 'raspr': list}
    - lock: блокировка для доступа к общим данным
    """
    # Для каждого процесса используем свой seed, чтобы последовательности не повторялись
    random.seed(time.time_ns() + pid)
    n = len(loads)
    fail_counter = 0 # счётчик неудачных попыток улучшения подряд для каждого процесса (уточнено у В.В Балашова)

    while fail_counter < 5000:

        # Генерируем случайное распределение
        raspr = [random.randrange(processors) for i in range(n)]

        # Вычисляем целевую функцию
        f = max_processor_load(raspr, loads, processors)

        # Проверяем корректность (нагрузка на процессор и сеть)
        if not is_valid(raspr, loads, processors, net_limit, comms):
            fail_counter += 1
            continue

        # Если распределение корректно, проверяем глобальное лучшее с блокировкой
        with lock:
            if f < best_dict['value']:
                best_dict['value'] = f
                best_dict['raspr'] = raspr[:]  # сохраняем копию
                fail_counter = 0
            else:
                fail_counter += 1

# Запускаем процессы
def parallel_search(processors, net_limit, loads, comms, num_forks, claster_flag):
    manager = mp.Manager()
    best_dict = manager.dict()  # общий словарь, в котором хранится лучшая функция и лучшее распределение
    best_dict['value'] = 101
    best_dict['raspr'] = None
    lock = mp.Lock()

    if claster_flag:
        claster_raspr = create_claster_raspr(processors, loads, comms)
        claster_f = max_processor_load(claster_raspr, loads, processors)
        if is_valid(claster_raspr, loads, processors, net_limit, comms) and claster_f < best_dict['value']:
            best_dict['value'] = claster_f
            best_dict['raspr'] = claster_raspr[:]

    processes = []
    for i in range(num_forks):
        p = mp.Process(target=fork, args=(processors, net_limit, loads, comms, best_dict, lock, i))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    return best_dict['raspr'], best_dict['value']

def main():
    if len(sys.argv) != 2:
        print("Использование: python mvs_dop.py <файл.xml>", file=sys.stderr)
        sys.exit(1)

    try:
        processors, net_limit, loads, comms = parsing(sys.argv[1])
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}", file=sys.stderr)
        sys.exit(1)

    # Параметры эксперимента
    forks_list = [1, 2, 4, 8]
    runs = 10
    random_times = {} # Словари массивов: ключ - количество процессов, значение - массив времен/функций
    random_fs = {}
    claster_times = {}
    claster_fs = {}
    itog_t = {}
    itog_f = {}

    for fork in forks_list:
        random_times[fork] = []
        random_fs[fork] = []
        claster_times[fork] = []
        claster_fs[fork] = []

        for r in range(runs):
            # Без кластеризации
            random.seed(r * 100 + fork)
            start = time.time()
            _, best_f = parallel_search(processors, net_limit, loads, comms, num_forks=fork, claster_flag=False)
            end = time.time()
            random_times[fork].append(end - start)
            random_fs[fork].append(best_f)

            # Кластеризация
            random.seed(r * 100 + fork + 1000)
            start = time.time()
            _, best_f = parallel_search(processors, net_limit, loads, comms, num_forks=fork, claster_flag=True)
            end = time.time()
            claster_times[fork].append(end - start)
            claster_fs[fork].append(best_f)
            
            print("run", r + 1, "/", runs, end ='\r')
        print()

        # Считаем среднее время и среднее значение f. Храним в словаре массивов:
        # 1: [среднее время рандом, среднее время кластера]
        sum_r_t = sum(random_times[fork])
        sum_c_t = sum(claster_times[fork])
        sum_r_f = sum(random_fs[fork])
        sum_c_f = sum(claster_fs[fork])
        itog_t[fork] = [sum_r_t / runs, sum_c_t / runs]
        itog_f[fork] = [sum_r_f / runs, sum_c_f / runs]

    # Подсчёт уменьшения/увеличения времени между двумя методами
    percent_results = {}
    for fork in forks_list:
        percent = (itog_t[fork][0] - itog_t[fork][1]) / itog_t[fork][0] * 100
        percent_results[fork] = percent

    # Вывод таблицы с уменьшением времени
    print("\nСнижение/увеличение времени между методами в % (положительное == кластер быстрее)")
    for fork in forks_list:
        print(f"{fork} forks: {percent_results[fork]:.2f}")

    # Построение диаграммы
    try:
        import matplotlib.pyplot as plt

        x = forks_list
        y = [percent_results[f] for f in forks_list]

        plt.figure(figsize=(8, 5))
        plt.bar([str(f) for f in x], y)
        plt.xlabel("Число процессов")
        plt.ylabel("Изменение времени, %")
        plt.title("Уменьшение времени выполнения между двумя типами в %")
        plt.grid(axis='y')
        plt.tight_layout()
        plt.savefig("chart.png")
        plt.show()
        print("\nДиаграмма сохранена в файл chart.png")
        
        random_f_avg = [itog_f[f][0] for f in forks_list]
        claster_f_avg = [itog_f[f][1] for f in forks_list]

        plt.figure(figsize=(8, 5))
        x = [str(f) for f in forks_list]
        width = 0.35
        plt.bar([i - width/2 for i in range(len(x))], random_f_avg, width, label='Random', color='skyblue')
        plt.bar([i + width/2 for i in range(len(x))], claster_f_avg, width, label='Clustering', color='orange')
        plt.xlabel('Количество процессов')
        plt.ylabel('Максимальная нагрузка CPU (%)')
        plt.title('Сравнение качества решения (чем ниже, тем лучше)')
        plt.xticks(range(len(x)), x)
        plt.legend()
        plt.grid(axis='y')
        plt.tight_layout()
        plt.savefig('quality_comparison.png')
        plt.show()
        print("Диаграмма качества сохранена в quality_comparison.png")
        
    except ImportError:
        print("\nmatplotlib не установлен, диаграмма не построена.", file=sys.stderr)

if __name__ == "__main__":
    main()
