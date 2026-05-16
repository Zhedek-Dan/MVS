import sys
import random
import xml.etree.ElementTree as ET
from sklearn.cluster import AgglomerativeClustering

# Читаем XML файл, проверка на корректность файла
def parsing(filename):
    allowed_loads = {4, 11, 14, 21}
    allowed_intensities = {0, 21, 49, 71, 99}

    try:
        tree = ET.parse(filename)
        root = tree.getroot()
    except FileNotFoundError:
        raise ValueError("Файл не найден")
    except ET.ParseError:
        raise ValueError("Некорректный XML файл")

    # Кол-во процессоров и максимальная возможная нагрузка на сеть
    processors_elem = root.find('processors')
    prog_count_elem = root.find('prog_count')
    net_limit_elem = root.find('net_limit')

    if processors_elem is None or processors_elem.text is None:
        raise ValueError("Отсутствует элемент <processors> или значение")
    if prog_count_elem is None or prog_count_elem.text is None:
        raise ValueError("Отсутствует элемент <prog_count> или значение")
    if net_limit_elem is None or net_limit_elem.text is None:
        raise ValueError("Отсутствует элемент <net_limit> или значение")

    try:
        processors = int(processors_elem.text)
        prog_count = int(prog_count_elem.text)
        net_limit = int(net_limit_elem.text)
    except ValueError:
        raise ValueError("Значения processors, prog_count и net_limit должны быть целыми числами")

    if processors <= 0:
        raise ValueError("Количество процессоров должно быть положительным")
    if prog_count <= 0:
        raise ValueError("Количество программ должно быть положительным")
    if net_limit < 0:
        raise ValueError("Максимальная нагрузка на сеть не может быть отрицательной")
    if net_limit % 100 != 0:
        raise ValueError("Максимальная нагрузка на сеть должна быть кратна 100")

    # Список нагрузок программ
    loads = []
    prog_elems = root.find('programs')
    if prog_elems is None:
        raise ValueError("Отсутствует элемент <programs>")

    ids = set()
    for prog in prog_elems.findall('program'):
        pid = prog.get('id')
        load = prog.get('load')

        if pid is None or load is None:
            raise ValueError("Каждая программа должна иметь атрибуты id и load")

        try:
            pid = int(pid)
            load = int(load)
        except ValueError:
            raise ValueError("Атрибуты id и load программы должны быть целыми числами")

        if pid <= 0:
            raise ValueError("id программы должен быть положительным")
        if pid in ids:
            raise ValueError(f"Повторяющийся id программы: {pid}")
        if load not in allowed_loads:
            raise ValueError(f"Недопустимая нагрузка программы: {load}")

        ids.add(pid)
        loads.append((pid, load))

    if not loads:
        raise ValueError("Список программ пуст")

    if len(loads) != prog_count:
        raise ValueError("Количество программ не совпадает со значением <prog_count>")

    loads.sort()
    expected_ids = list(range(1, len(loads) + 1))
    actual_ids = [pid for pid, load in loads]
    if actual_ids != expected_ids:
        raise ValueError("id программ должны идти подряд от 1 до N")

    loads = [load for pid, load in loads]

    # Список обменов
    comms = []
    comm_elems = root.find('communications')
    if comm_elems is None:
        raise ValueError("Отсутствует элемент <communications>")

    used_pairs = set()
    for comm in comm_elems.findall('comm'):
        from_id = comm.get('from')
        to_id = comm.get('to')
        intensity = comm.get('intensity')

        if from_id is None or to_id is None or intensity is None:
            raise ValueError("Каждая связь должна иметь атрибуты from, to, intensity")

        try:
            from_id = int(from_id)
            to_id = int(to_id)
            intensity = int(intensity)
        except ValueError:
            raise ValueError("Атрибуты from, to, intensity должны быть целыми числами")

        if from_id == to_id:
            raise ValueError("Программа не может обмениваться сама с собой")
        if from_id < 1 or from_id > len(loads) or to_id < 1 or to_id > len(loads):
            raise ValueError("Связь содержит несуществующий id программы")
        if intensity not in allowed_intensities:
            raise ValueError(f"Недопустимая интенсивность обмена: {intensity}")

        pair = tuple(sorted((from_id, to_id)))
        if pair in used_pairs:
            raise ValueError(f"Повторяющаяся связь между программами: {pair}")
        used_pairs.add(pair)

        from_id -= 1  # Чтобы получились индексы с 0
        to_id -= 1
        comms.append((from_id, to_id, intensity))

    return processors, net_limit, loads, comms

# Максимальная нагрузка на процессоры
def max_processor_load(statmas, loads, processors):
    sums = [0] * processors
    for prog, proc in enumerate(statmas):
        sums[proc] += loads[prog]
    return max(sums)

# Нагрузка сети
def network_load(statmas, comms):
    total = 0
    for i, j, k in comms:
        if statmas[i] != statmas[j]:
            total += k
    return total

# Проверка на перегрузку процессоров/сети
def is_valid(statmas, loads, processors, net_limit, comms):

    # Нагрузка на процессоры
    sums = [0] * processors
    for prog, proc in enumerate(statmas):
        sums[proc] += loads[prog]
    if any(s > 100 for s in sums):
        return False

    # Нагрузка на сеть
    if network_load(statmas, comms) > net_limit:
        return False
    return True

def create_claster_raspr(processors, loads, comms):
    """
    Построим начальное распределение программ по процессорам,
    используя кластеризацию на основе интенсивности обмена. (большие интенсивности закинем в один кластер и этому кластеру поставим в соответствие процессор)
    Возвращает список длины N, где значение i – номер процессора (0..processors-1).
    """
    n = len(loads)
    # Матрица интенсивностей
    intens = [[0 for i in range(n)] for j in range(n)]
    for i, j, w in comms:
        intens[i][j] = intens[j][i] = w

    # Преобразуем интенсивность в расстояние: d = 1/(1 + w)
    # Формула: чем больше интенсивность между программами, тем меньше расстояние между ними
    dist = [[0 for i in range(n)] for j in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            w = intens[i][j]
            if w > 0:
                d = 1.0 / (1 + w)
            else:
                d = 1.0             # нет обмена => далеко
            dist[i][j] = dist[j][i] = d

    clustering = AgglomerativeClustering(
        n_clusters=processors,
        metric='precomputed',
        linkage='average'
    )
    labels = clustering.fit_predict(dist)
    return labels.tolist()
    
# Случайный поиск
def random_search(processors, net_limit, loads, comms):
    n = len(loads)
    best_f = 101
    best_raspr = [-1] * n
    predel = 0
    count = 0
    while predel < 5000:
        # Случайное распределение, i - программа, raspr[i] - процессор, которому принадлежит программа (похоже на массив статистики)
        raspr = [random.randrange(processors) for i in range(n)]
        count += 1

        f = max_processor_load(raspr, loads, processors)

        # Превысили целевую функцию
        if f >= best_f:
            predel += 1
            continue

        # Распределение не подходит под условия
        if not is_valid(raspr, loads, processors, net_limit, comms):
            predel += 1
            continue

        # Нашли лучшее корректное решение
        best_raspr = raspr[:]
        best_f = f
        predel = 0

    return best_raspr, best_f, count

if __name__ == "__main__":
	if len(sys.argv) != 2:
	    print("Использование: python mvs_.py <файл.xml>", file=sys.stderr)
	    sys.exit(1)
	
	try:
	    processors, net_limit, loads, comms = parsing(sys.argv[1])
	except ValueError as e:
	    print(f"Ошибка входных данных: {e}", file=sys.stderr)
	    sys.exit(1)
	
	# На всякий случай, чтобы набор был точно разным
	random.seed()

	best_raspr, best_f, count = random_search(processors, net_limit, loads, comms)

	if best_raspr == [-1] * len(best_raspr):
	    print("FAILED")
	    print(count)
	else:
	    print("SOLVED")
	    print(count)
	    best_raspr = [p + 1 for p in best_raspr]  # Возвращаем номер процессора (randrange берет номер от 0 до prosessors - 1)
	    print(" ".join(map(str, best_raspr)))
	    print(best_f)

