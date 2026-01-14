# OCR Benchmarks — 数据与脚本整理

本仓库用于管理用于 OCR 基准测试的数据、脚本和结果。当前结构旨在清晰划分数据资产、脚本实现及文档。

## 目录结构
- `data/` 资产与产出（数据集、日志、报告、字体等）
- `scripts/` 脚本骨架（数据生成、评测、汇总占位）
- `docs/` 说明与记录（如有）
- `README.md`、`.gitignore` 根级文档

## 快速开始
- 环境：Python 3.x（建议使用虚拟环境）
- 安装依赖：如有 `requirements.txt`，请执行 `pip install -r requirements.txt`
- 数据布局：数据与产出统一放在 `data/` 下，避免将大数据直接推送到仓库
- 运行占位脚本：
  - `python scripts/generate_placeholder.py`
  - `python scripts/evaluate_placeholder.py`
  - `python scripts/aggregate_placeholder.py`

## 数据整理指南
- 本地整理：已将根目录内容整理为 `data/`，根目录仅保留数据资产及脚本骨架
- 添加新数据：将数据放入 `data/` 的合适子目录，并在 `scripts/` 实现相应的导入/处理逻辑

## 贡献
- 如需贡献，请在此基础上实现具体的数据生成、评测和汇总脚本，并遵循团队的代码风格与贡献指南。