# Git 手动流程（网络不稳时）

这份文档是给“网络不稳定”场景用的。
你可以按顺序执行，直到推送成功。

## 1. 查看当前状态

```
git status -sb
```

## 2. 查看变更内容（可选）

```
git diff
```

## 3. 添加改动

```
git add .
```

## 4. 提交

```
git commit -m "这里写你的提交说明"
```

示例：

```
git commit -m "fix: support Render port"
```

## 5. 推送

```
git push
```

如果推送失败（比如网络被重置），只需要重复执行 `git push`。
