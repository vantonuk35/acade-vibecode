import fitz  
import requests
from io import BytesIO

PDF_URL = "https://onlinejudge.org/external/***"
LLAMA_SERVER_URL = "http://127.0.0.1:1234/v1/completions"

def download_pdf(url: str) -> fitz.Document:
    response = requests.get(url)
    response.raise_for_status()
    return fitz.open(stream=BytesIO(response.content), filetype="pdf")

def extract_text_with_font_sizes(doc: fitz.Document) -> str:
    chunks = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    size = int(round(span["size"]))
                    chunks.append(f"[size={size}]{text}[/size]")
                chunks.append("\n")
            chunks.append("\n")
    return "".join(chunks)

def make_prompt(text: str) -> str:
    return f"""
You are a helpful assistant that extracts and formats programming problems from PDF documents.

Your task is to convert raw OCR-style extracted text into a clean HTML representation.

Rules:
- Wrap all mathematical expressions in \\(...\\)
- Subscripts must be rendered as _{{...}}, superscripts as ^{{...}}
- Italic formatting can be applied semantically using <i>...</i>
- Use the following section labels: <b>Problem Statement</b>, <b>Input</b>, <b>Output</b>, <b>Sample Input</b>, <b>Sample Output</b>
- Wrap sample input/output in <pre>...</pre> tags
- Use plain HTML only — no <div>, <br>, or markdown
- Do not include the [size=...] markers in the output

Start the output like this:
<b>Problem Statement</b>
...

Here is the raw extracted text:
{text}

Now produce the cleaned HTML version below:
"""

# === Шаг 3. Отправляем запрос в llama.cpp сервер ===
def query_lmstudio_completion(prompt: str, model: str = "local-model", max_tokens: int = 2048, temperature: float = 0.2) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop": ["</html>", "</s>"]
    }
    response = requests.post("http://127.0.0.1:1234/v1/completions", json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["text"].strip()

pdf = download_pdf(PDF_URL)
raw_text = extract_text_with_font_sizes(pdf)
prompt = make_prompt(raw_text)
html_output = query_lmstudio_completion(prompt)

print(html_output)

html_output[:3000]
