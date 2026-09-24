# 修复 index.html 中的 JSON 损坏问题（实际换行符未转义）
import json, re, sys

html_path = r"D:\0-WorkBuddy\ai-news-site\index.html"
with open(html_path, encoding="utf-8") as f:
    c = f.read()

m = re.search(r"const DATA = (\{.+?\});\s*const WEEK", c, re.DOTALL)
if not m:
    print("未找到 DATA 块，尝试用 generate.py 重建...")
    sys.exit(1)

raw = m.group(1)
# 状态机：把 JSON 字符串值内的真实换行替换为 \n
in_str = False
esc = False
out = []
for ch in raw:
    if esc:
        out.append(ch)
        esc = False
        continue
    if ch == "\\":
        esc = True
        out.append(ch)
        continue
    if ch == '"':
        in_str = not in_str
        out.append(ch)
        continue
    if ch == "\n" and in_str:
        out.append("\\n")
    else:
        out.append(ch)

fixed = "".join(out)
try:
    d = json.loads(fixed)
except Exception as e:
    print("JSON 解析失败:", e)
    sys.exit(1)

print("JSON 修复 OK")
print("ai:", len(d["ai"]["items"]), "sports:", len(d["sports"]["items"]), "mil:", len(d["mil"]["items"]))

# 验证并写回
new_data = json.dumps(d, ensure_ascii=False)
new_html = c[:m.start()] + "const DATA = " + new_data + ";\s*const WEEK" + c[m.end():]
with open(html_path, "w", encoding="utf-8") as f:
    f.write(new_html)
print("已写回", html_path)

# 抽检 meta takes down 那条
for it in d["ai"]["items"]:
    t = (it.get("title") or "")
    if "takes down" in t.lower():
        print("\n--- meta takes down 条目 ---")
        for k in ("title", "summary", "full", "title_zh", "summary_zh", "full_zh"):
            v = (it.get(k) or "").replace("\n", "\\n")
            print(k + ":", v[:200])
        break
