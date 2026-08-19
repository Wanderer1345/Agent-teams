# 在全新电脑上运行

## 关键前提（先看这几条，避免踩坑）

1. **要整个 `localization-agents/` 文件夹**：代码用相对路径读 `../teams/`(agent 定义) 和 `../data/`(术语库/TM)，不能只拷 `langgraph_impl/`。
2. **不要拷 `.venv/`**：它绑定原机器路径，换机必须重建。
3. **`.env` 含密钥**：建议不要直接拷，用 `.env.example` 重新生成并填新 key（旧 key 应作废）。
4. **需要 Python ≥ 3.10**（langgraph 要求）；系统自带的 Python 3.9 不行。
5. 确认 `teams/ux-writer/agents/*.md` 和 `teams/reviewer/agents/*.md` 存在；若只有 `teams.zip`，先解压：
   `cd localization-agents && unzip -o teams.zip -x "__MACOSX/*"`

---

## macOS

```bash
# 1) 装 Homebrew（已有可跳过）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2) 装 Python 3.12
brew install python@3.12

# 3) 进项目
cd /路径/localization-agents/langgraph_impl

# 4) 建 venv + 装依赖
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv
./.venv/bin/pip install -r requirements.txt

# 5) 配 .env
cp .env.example .env
open -e .env          # 填模型 key（+ 可选 LangSmith key），保存

# 6) 跑
./.venv/bin/python run_demo.py                              # 桩：无需 key，验证链路
./.venv/bin/python run_demo.py --submission my_input.json   # 真实模型
```

## Windows

```powershell
# 1) 从 python.org 安装 Python 3.12（勾选 Add to PATH）
# 2) 进项目
cd \路径\localization-agents\langgraph_impl
# 3) 建 venv + 装依赖
py -3.12 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
# 4) 配 .env：复制 .env.example 为 .env，用记事本填 key
copy .env.example .env
notepad .env
# 5) 跑
.\.venv\Scripts\python run_demo.py
.\.venv\Scripts\python run_demo.py --submission my_input.json
```

## Linux

```bash
sudo apt install -y python3.12 python3.12-venv    # 或用发行版对应方式
cd /路径/localization-agents/langgraph_impl
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
./.venv/bin/python run_demo.py
```

---

## 验证是否装好

```bash
./.venv/bin/python -c "import langgraph, langchain_core; print('ok')"
```

无 key 直接 `run_demo.py` 能打印出 Team A→Team B 链路，即环境就绪。
之后填好 `.env` 的模型 key 即可走真实模型；填 LangSmith key 即可在 smith.langchain.com 看链路。
