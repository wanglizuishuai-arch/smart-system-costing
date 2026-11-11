# 发布到 GitHub（三步，约 60 秒）

仓库已经在本地建好并完成首次提交，**只差一个远端**。

## 前置

- 已装 git（本机 2.54），已配 `credential.helper=manager`（首次 push 会弹浏览器登录）
- 没有装 `gh` CLI，所以下面用「网页建仓 + git push」的方式

## 第 1 步：在 GitHub 建一个空仓库

打开 <https://github.com/new>：

| 字段 | 填什么 |
|---|---|
| Repository name | `smart-system-costing` |
| Description | 智能化项目方案与投资估算技能：口径、算量、清单取费、对账、毛利 |
| 可见性 | 建议 **Public**（方法类仓库，公开才有复用价值） |
| Initialize | **一个都不要勾**（不要 README / .gitignore / LICENSE，否则会冲突） |

## 第 2 步：加远端并推送

```powershell
cd "D:\Deepseek Work\output\gh\smart-system-costing"
git remote add origin https://github.com/<你的用户名>/smart-system-costing.git
git push -u origin main
```

首次 push 会弹出 Git Credential Manager 的浏览器授权窗口，登录一次即可，之后凭据由 Windows 凭据管理器保存。

## 第 3 步：验证

```powershell
git remote -v
git ls-remote origin        # 应看到 refs/heads/main
```

到仓库页面确认：

- [ ] 首页 README 正常渲染（含"密钥防泄露"一节）
- [ ] `scripts/costing_check.py` 能看到
- [ ] Actions 页出现 `keyguard` 工作流，且首次运行通过
- [ ] 仓库文件列表里没有 `.docx / .xlsx / .pdf` 等业务文件

## 如果 push 被拒

| 现象 | 原因 | 处理 |
|---|---|---|
| `remote: Repository not found` | 仓库没建 / 用户名写错 / 无权限 | 核对 URL，确认已建仓且为空 |
| `Updates were rejected` | 建仓时勾了 README，远端已有提交 | `git pull --rebase origin main` 后重推 |
| 弹不出登录窗口 | GCM 未生效 | `git config --global credential.helper manager` 后重试 |
| `Permission denied (publickey)` | 远端用了 SSH 地址 | 换成 `https://` 地址 |

## 事后（可选）

- 打 tag：`git tag v0.1.0 && git push origin v0.1.0`
- 开 Issues / Discussions，把「不同地区单价差异」「GB/T 50856 工程量计算」列为待补
- 若日后要给他人分发，按 ai-bid-document 的经验：**打 zip 时去掉无扩展名文件**（LICENSE / VERSION / .gitignore / .github），很多技能市场会拒收