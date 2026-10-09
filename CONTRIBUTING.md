# Contributing to Causal-IDFM Identification

本文件描述学生与维护者的基本 GitHub 协作流程。

## 1. 不直接修改 main

`main` 是稳定分支。学生不得直接 push `main`；所有改动通过 Pull Request 审核。

第一轮任务建议统一从冻结 tag 开始：

```bash
git fetch origin --tags
git checkout -b task/01-short-description student-task1-baseline
```

branch 命名建议：

```text
task/01-heterogeneous-bernoulli-majority
task/02-heterogeneous-bernoulli-three-level
...
```

如果多人可能负责同一个 Task，可在末尾加姓名或 GitHub handle。

## 2. Task 1：优先隔离学习产物

第一次任务主要是熟悉 Identification 与验证流程。除非任务明确要求修改共享 core，建议把
standalone deliverables 放在：

```text
student_work/taskXX/
```

不要为了完成练习随意修改 Estimation / Policy。

如果你认为自己的实现应该进入共享 Identification core，请在 PR 的 **Reusability** 部分明确说明：

- 它抽象了什么共同规律；
- 为什么不是只对你的 setting hard-code；
- 哪些其他任务可以复用；
- 新增了哪些 tests。

## 3. 开发前先确认范围

主要可修改：

```text
pfn_pipeline/identification.py
pfn_pipeline/_internal/identification/**
tests/test_identification_integration.py
student_work/taskXX/**
```

需要额外说明后才能修改：

```text
pfn_pipeline/contracts.py
```

默认不要修改：

```text
pfn_pipeline/_internal/estimation/**
pfn_pipeline/_internal/policy/**
pfn_pipeline/estimation.py
pfn_pipeline/policy.py
```

## 4. Commit 规则

推荐小而有意义的 commit，例如：

```text
Add complete-randomization support calculation
Add brute-force oracle tests for three-level exposure
Document zero-support behavior for Task 04
```

避免只有 `fix`, `update`, `final`, `final2` 这类不可读 commit message。
维护者最终可以使用 Squash and merge，因此不要求学生把本地历史整理得非常复杂。

## 5. 提交前测试

正式任务定义和验收要求以群内发布的任务书为准；任务索引见 `docs/student_tasks/`，当前接口说明见
`docs/IDENTIFICATION_INTERFACE.md`。

至少运行当前 Identification tests：

```bash
python -B -m unittest discover -s tests -p "test_identification_integration.py" -v
```

如果修改了公共 contract、handoff，或任何会影响完整 pipeline 的代码，再运行：

```bash
python -B -m unittest discover -s tests -p "test_pipeline_smoke.py" -v
```

每个 `student_work/taskXX/` 目录必须包含 `test_rule.py` 或其他 `test_*.py` 测试文件。
在仓库根目录运行下面的命令，会逐个任务执行测试；请在 PR 中报告结果：

```bash
python -B tools/run_student_tests.py
```

测试可使用 pytest 函数或 unittest 测试类。不同任务在独立进程中运行，因此多个任务都使用
`support.py`、`rule.py`、`test_rule.py` 这些文件名不会互相串用模块。
尚无任务目录时跳过；已有任务目录但缺少测试、未收集到测试或测试失败时，检查失败。

GitHub Actions 会在 PR 上重复运行仓库 regression tests 和上述学生任务测试。**CI 通过是 merge 的必要条件之一，
但不是充分条件**：theorem、assumptions、support 与是否值得进入共享 API 仍需要人工 review。

## 6. 不要提交运行产物

以下文件应保持本地：

```text
checkpoints/
outputs/
.cache/
.ipynb_checkpoints/
.virtual_documents/
*.pt
*.pth
*.ckpt
```

如果 `git status` 出现大模型、训练输出或 notebook checkpoint，请在 commit 前删除/取消跟踪。

## 7. Push 与 Pull Request

完成后：

```bash
git status
git add <relevant files>
git commit -m "Your meaningful commit message"
git push -u origin <your-branch-name>
```

然后在 GitHub 创建 **Draft Pull Request**。自查完成后再标记为 **Ready for review**。

PR 必须使用仓库模板，至少写清楚：

- assigned task / setting；
- causal target；
- assumptions；
- support；
- 为什么是 POINT（如果本任务属于当前 POINT family）；
- 如何验证；
- 修改了哪些文件；
- 哪些内容具有复用价值；
- 已知限制。

## 8. Review 结果

PR 有三种正常结果：

### A. Approve + merge

数学正确、实现可复用、测试充分，适合进入共享 Identification codebase。

### B. Request changes

思路可能正确，但需要修正数学、接口、测试或抽象方式；学生在同一 branch 继续 push，PR 会自动更新。

### C. Review complete + close without merge

任务本身完成且内容正确，但实现主要属于学习验证、与已有代码重复、或暂时不适合作为共享 API。
这不等于任务失败。

> **Task completion ≠ merge into main.**

PR 是 review unit；`main` 是稳定 product/research codebase。

## 9. 保持与 main 同步

第一轮任务统一从 `student-task1-baseline` 起步即可，不要求频繁 rebase。

后续长期任务在 review 前如果 main 已发生较大变化，可以：

```bash
git fetch origin
git checkout <your-branch>
git merge origin/main
```

对初学者优先使用 merge；不要在不理解后果时对已经共享的 branch 做 force push。
