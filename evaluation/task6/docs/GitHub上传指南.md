# 任务6 GitHub上传指南

当前仓库目录：`<仓库目录>`。当前本地分支是`task6-llm-evaluation`，remote `fork`指向`yuehan19777/CFM-identification`，`origin`指向`zzyyLOGIC/CFM-identification`。执行前用下面命令复核，若输出不同先停下检查。

## 1. 需要提交哪些文件

在确认每个文件适合公开之后，提交 `evaluation/task6/` 和以下项目代码：

- `cfm_id_llm/compact_response_contract.py`：注册可选配置；
- `cfm_id_llm/target_first_skill_guarded.py`：追加受请求哈希绑定的提示。
- `cfm_id/intake_conflict_review.py`、`cfm_id/project.py`：审核确认冲突后的追问入口。

- `__init__.py`、`README_ZH.md`：包入口和当前状态；
- `materials/`：24份测试输入；`references/`：24份待审参考草稿；
- `scripts/`：评测、评分、事实台账、N01链路、离线收尾和快照恢复脚本；
- `tests/`：离线测试；
- `docs/`：评分口径、审查待办、参考审读空表、PR说明和本指南；
- `results/20261105/`：已有脱敏统计、失败清单、配置与Skill快照、证据哈希及历史报告。
- `pilot_cases/`、`corrected_cases/`、`results/20261108/`、`results/20261110/`：虚构试点、修正后的题目及分阶段报告。

下面这些**不提交**：整个`outputs/`（含私有请求、模型输出、AI预审、恢复候选、N01审核数据）；根目录的`task6_holdout_32_results.zip`、`fix_n01_fact_candidate.py`、`task6_n01_fullchain.py`；任何API密钥、`.env`或含密钥的日志。必要的N01链路脚本已放在`evaluation/task6/scripts/n01_fullchain.py`。单题候选可以在受控环境供审读，公开前需确认脱敏。

## 2. 检查、暂存、提交

在PowerShell逐行运行：

先确认 Python 为 3.11 及以上，且 Pydantic 满足仓库的 `>=2.12,<3`；可在项目虚拟环境安装仓库依赖后执行测试，例如 `python -m pip install -e .`。本次检查使用 Pydantic 2.14.2。

```powershell
cd <仓库目录>
git status --short --branch
git remote -v
python -m unittest discover -s evaluation/task6/tests -v
git add --dry-run -- evaluation/task6/ cfm_id_llm/compact_response_contract.py cfm_id_llm/target_first_skill_guarded.py cfm_id/intake_conflict_review.py cfm_id/project.py
git add -- evaluation/task6/ cfm_id_llm/compact_response_contract.py cfm_id_llm/target_first_skill_guarded.py cfm_id/intake_conflict_review.py cfm_id/project.py
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
```

确认暂存列表只包含上述文件，并检查暂存内容里没有密钥或私有回答。若出现其他已暂存文件，**不要运行下一条提交命令**；先通过Git界面或`git restore --staged -- <具体文件>`移除那些暂存项，保留工作区文件。确认无误后：

```powershell
git commit -m "Add Task 6 reading evaluation and audit"
git push -u fork task6-llm-evaluation
```

若提示身份未设置，用你自己的GitHub身份配置`git config user.name`和`git config user.email`；若身份验证失败，用GitHub Desktop或Git Credential Manager登录。若网络不可达，恢复网络后重试push；不要把密钥写进命令行、README或远程地址。

## 3. 更新已有PR

已有 [PR #10](https://github.com/zzyyLOGIC/CFM-identification/pull/10)：向你的 fork 的同一 `task6-llm-evaluation` 分支推送后，它会自动更新，无需再开新 PR。复制 `docs/PR说明.md` 的内容更新已有 PR，明确尚未完成的验收。核对 Files changed 和敏感信息，等待负责人审核；该指南不表示已获得通过。

## 4. 当前边界

如果原项目主分支已更新，先在GitHub比较差异；合并由维护者处理。当前修改仍在本地，尚未为这轮修改执行 commit 或 push；使用本指南前请核对远端及现有PR状态。
