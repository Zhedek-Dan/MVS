import sys
import random
import xml.etree.ElementTree as ET
from xml.dom import minidom


def generate_xml(processors: int, output_file: str):

    # Входные данные
    programs = processors * random.randint(6, 10)
    net_limit = random.randrange(100, 20000, 100)
    allowed_loads = [4, 11, 14, 21]
    while True:
    	loads = [random.choice(allowed_loads) for i in range(programs)]
    	if sum(loads)/processors > 40:
    		break 

    # Создание XML файла
    root = ET.Element("mvs")
    ET.SubElement(root, "processors").text = str(processors)
    ET.SubElement(root, "prog_count").text = str(programs)
    ET.SubElement(root, "net_limit").text = str(net_limit)

    # Секция программ
    progs = ET.SubElement(root, "programs")
    for i in range(1, programs + 1):
        prog = ET.SubElement(progs, "program")
        prog.set("id", str(i))
        prog.set("load", str(loads[i-1]))

    # Секция связей
    comm_elem = ET.SubElement(root, "communications")
    used_pairs = set()

    # Обязательные пары (минимум 2 на программу)
    for i in range(1, programs + 1):
        candidates = [x for x in range(1, programs + 1) if x != i]
        partners = random.sample(candidates, 2)
        for partner in partners:
            pair = tuple(sorted((i, partner)))
            if pair not in used_pairs:
                used_pairs.add(pair)
                intens = random.choice([21, 49, 71, 99])
                comm = ET.SubElement(comm_elem, "comm")
                comm.set("from", str(pair[0]))
                comm.set("to", str(pair[1]))
                comm.set("intensity", str(intens))

    # Дополнительные пары
    extra_pairs = random.randint(programs // 2, programs * 2)
    for i in range(extra_pairs):
        p1, p2 = random.sample(range(1, programs + 1), 2)
        pair = tuple(sorted((p1, p2)))
        if pair not in used_pairs:
            used_pairs.add(pair)
            intens = random.choice([0, 21, 49, 71, 99])
            comm = ET.SubElement(comm_elem, "comm")
            comm.set("from", str(pair[0]))
            comm.set("to", str(pair[1]))
            comm.set("intensity", str(intens))

    # Записываем XML в файл с отступами
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent="  ")
    # Убираем лишнюю строку <?xml ...>
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(pretty_xml)


# Перенос аргументной строки
if len(sys.argv) != 3:
    print("Использование: python3 generate_input.py <processors> <output.xml>", file=sys.stderr)
    sys.exit(1)

try:
    cps = int(sys.argv[1])
    output = sys.argv[2]
except ValueError:
    print("Ошибка: processors должно быть целым числом", file=sys.stderr)
    sys.exit(1)

if cps <= 0:
    print("Ошибка: processors должно быть положительным", file=sys.stderr)
    sys.exit(1)

generate_xml(cps, output)

print(f"Файл {output} успешно создан.")
