#!/bin/zsh
# 使用本目录虚拟环境；安装依赖请按 README 明确执行。
cd -- "${0:A:h}" || exit 1
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python run.py "$@"
fi
print '请先按 README 创建 .venv 并安装 requirements-dev.txt，然后再次启动。'
exit 1
