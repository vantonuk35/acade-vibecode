import requests
import json
from bs4 import BeautifulSoup

def extract_json_array_from_push(script_text: str) -> str:
    push_marker = "self.__next_f.push("
    start_idx = script_text.find(push_marker)
    if start_idx == -1:
        return None
    array_start = script_text.find("[", start_idx)
    if array_start == -1:
        return None
    bracket_count = 0
    for i in range(array_start, len(script_text)):
        if script_text[i] == "[":
            bracket_count += 1
        elif script_text[i] == "]":
            bracket_count -= 1
            if bracket_count == 0:
                return script_text[array_start:i+1]
    return None

def extract_problem_json_from_nested_string(array_data):
    for item in array_data:
        if isinstance(item, str) and '"__typename":"Problem"' in item:
            fixed = item
            try:
                parsed = json.loads(fixed[2:])
                if isinstance(parsed, list) and len(parsed) >= 4:
                    value = parsed[3].get("value")
                    if value and value.get("__typename") == "Problem":
                        return value
            except json.JSONDecodeError:
                continue
    raise ValueError("Не удалось распарсить JSON с '__typename': 'Problem'")

def extract_problem_data_from_script(url: str) -> dict:
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    target_script = None
    for script in soup.find_all("script"):
        if script.string and '\\"__typename\\":\\"Problem\\"' in script.string:
            target_script = script.string
            break
    if not target_script:
        raise ValueError("Не найден script с данными задачи")
    json_array_text = extract_json_array_from_push(target_script)
    if not json_array_text:
        raise ValueError("Не удалось извлечь содержимое push(...)")
    array_data = json.loads(json_array_text)
    return extract_problem_json_from_nested_string(array_data)

# ---------- ECM to HTML -----------

def render_ecm_to_html(children) -> dict:
    sections = {
        "legend": "",
        "input": "",
        "output": "",
        "note": ""
    }
    section_map = {
        "problem-input": "input",
        "problem-output": "output",
        "problem-note": "note"
    }
    current = "legend"
    for node in children:
        t = node.get("type")
        if t in section_map:
            current = section_map[t]
            inner = node.get("children", [])
            for inner_node in inner:
                html = render_node(inner_node)
                if html:
                    sections[current] += html
            continue
        if t == "problem-examples":
            # Примеры обрабатываем отдельно позже
            continue
        html = render_node(node)
        if html:
            sections[current] += html
    return sections

def render_node(node):
    t = node.get("type")
    if t == "p":
        return render_inline_children(node.get('children', [])) + "\n\n"
    elif t == "heading":
        text = render_inline_children(node.get("children", []))
        return f"<b>{text}</b>\n\n"
    elif t == "ul":
        items = ''.join(f"<li>{render_inline_children(item.get('children', []))}</li>" for item in node.get("children", []))
        return f"<ul>{items}</ul>\n"
    elif t == "ol" or t == "list":
        items = ''.join(f"<li>{render_inline_children(item.get('children', []))}</li>" for item in node.get("children", []))
        return f"<ol>{items}</ol>\n"
    elif t == "problem-attachments":
        return ""
    elif t == "problem-constraints":
        attr = node.get("attr", {})
        limits = []
        if "time-limit-min" in attr:
            cp = float(attr['cpu-limit-min'])
            tm = float(attr['time-limit-min'])
            limits.append(f"Ограничение по времени: {max(cp,tm)} мс")
        if "memory-limit-min" in attr:
            mem_mb = int(attr["memory-limit-min"]) / 1024 / 1024
            limits.append(f"Ограничение по памяти: {mem_mb:.0f} МБ")
        return "<b>" + ", ".join(limits) + "</b>\n\n"
    return ""

def render_inline_children(children):
    result = ""
    for child in children:
        t = child.get("type")
        attr = child.get("attr", {})
        text = attr.get("text", "")
        style = attr.get("style", "")
        if t == "p":
            result += render_inline_children(child.get('children', [])) + "\n\n"
        if t == "inline-math":
            result += f"\\({attr['exp']}\\)"
        if t == "inline-code":
            result += f"<code>{attr['source']}</code>"
        elif style == "bold":
            result += f"<b>{text}</b>"
        elif style == "italic":
            result += f"<i>{text}</i>"
        else:
            result += text
    return result

def fetch_url_text(url):
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.text.strip()
    except:
        return ""

# ---------- Main parse function -----------

def parse_full_problem(problem_data: dict) -> dict:
    content = problem_data["statement"]["content"]["render"]["children"]
    rendered = render_ecm_to_html(content)
    title = problem_data["statement"].get("title", "")

    # парсинг семплов из problem-examples
    examples_html = ""
    for node in content:
        if node.get("type") != "problem-examples":
            continue
        for i, example in enumerate(node.get("children", []), 1):
            attr = example.get("attr", {})
            input_url = attr.get("input-ref")
            output_url = attr.get("output-ref")
            input_data = fetch_url_text(input_url) if input_url else ""
            output_data = fetch_url_text(output_url) if output_url else ""
            examples_html += (
                f"<b>Пример {i}:</b>\n"
                f"<b>Ввод:</b>\n<pre>{input_data}</pre>\n"
                f"<b>Вывод:</b>\n<pre>{output_data}</pre>\n"
            )

    if examples_html:
        rendered["note"] += examples_html

    return {
        "Название задачи": title,
        "Условие": rendered["legend"].strip(),
        "Входные данные": rendered["input"].strip(),
        "Выходные данные": rendered["output"].strip(),
        "Примечание": rendered["note"].strip()
    }

# ---------- CLI / Test run -----------

if __name__ == "__main__":
    url = "https://basecamp.eolymp.com/ru/problems/8434"
    problem_data = extract_problem_data_from_script(url)
    parsed = parse_full_problem(problem_data)

    for key, value in parsed.items():
        print(f"<b>{key.upper()}</b>\n{value}\n")
