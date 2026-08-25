# 核对说明

本组在历史筛选阶段停止，没有可重放的三臂实验。FSE 工作簿没有保存三个目标仓的精确 Git 修订，三个仓的全部可达历史也都没有固定 Script Security 1.72 的维护者恢复；任选历史提交并手工提高 Jenkins 基线会生成数据集作者合成的 A2。

因此不应把 `replay_performed: false` 理解为缺失执行。包内可核对的是候选框、完整失败堆栈归类和全引用历史裁决：

```bash
jq -c . candidate-frame.jsonl
jq -c . root-audit.jsonl
jq . history-evidence.json
```

若重新审计目标历史，克隆、远程引用和临时文件必须放在项目内 `.work/script-security-1.72-fse/`。对每个镜像核对全部引用，而不是只检查默认分支：

```bash
git for-each-ref --format='%(refname)' | wc -l
git rev-list --all | sort -u | wc -l
git log --all -G'1[.]72' --format='%H %aI %s' -- \
  '*.xml' '*.gradle' '*.properties'
```

最后一条在三个目标仓中均无输出。它只支持“目标历史未声明固定 1.72”，不能据此构造兼容性负例。
