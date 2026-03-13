## 🏫 数字 FAFU 自动签到助手 (FAFU Auto Sign)

![alt text](https://img.shields.io/badge/Python-3.8+-blue.svg)    ![alt text](https://img.shields.io/badge/License-MIT-green.svg)    ![alt text](https://img.shields.io/badge/Status-Stable-brightgreen.svg)

本项目是针对福建农林大学与华为 WeLink 合作推出的“数字FAFU” APP 所编写的**自动签到程序**。通过逆向分析其前端加密逻辑，本项目实现了完全脱离 APP 的纯接口级自动化签到。

### ✨ 核心特性
✅ **完美逆向签名算法**：内置已被破解的 ```Authorization``` 请求头动态加密生成规则（MD5+Base64），无缝伪装官方 APP 请求。

✅ **心跳保活机制 (Keep-Alive)**：通过定时发送轻量级请求，保持后端 Session 存活，**彻底解决 Token 短期过期问题，实现一次抓包，一劳永逸！**

✅ **智能任务识别**：自动遍历任务列表，根据时间戳与关键词精准识别当前有效的“晚归签到”任务，过滤历史过期任务。

✅ **防封控策略 (Anti-Ban)**：提交签到时自动为经纬度添加安全范围内的随机偏移量（Float微调），模拟真实人类定位的GPS漂移现象。

✅ **自动图片上传**：支持自动读取同目录下的宿舍照片，对接七牛云接口实现静默上传与签到绑定。

### 🚨 免责声明 (Disclaimer)
1. 本项目开源仅为 Python 网络爬虫、JS 逆向工程及自动化测试技术的**学习与学术交流**。
2. 请遵守学校相关管理规定，切勿用于恶意逃避考勤与监管。
3. **使用者因滥用本项目引发的一切后果与责任由使用者本人自行承担，开发者不承担任何直接或间接责任**。

### 🛠️ 快速开始

1. **环境准备**

    请确保你的电脑或服务器已安装 Python 3.8 或更高版本。

2. **安装**
    ```bash
    # 克隆项目
    git clone https://github.com/yourusername/fafu_auto_sign.git
    cd fafu_auto_sign

    # 以可编辑模式安装
    pip install -e .
    ```

3. **获取你的专属 USER_TOKEN (需抓包)**

    由于涉及华为 WeLink 企业级授权，首次使用需手动抓取属于你的 Token：
    1. 在手机上安装抓包工具（如 iOS 的 Stream，Android 的 ProxyPin/HttpCanary 或电脑端的 Fiddler/Charles）。
    2. 开启抓包，打开"数字FAFU" APP，进入"签到"页面刷新一下。
    3. 在抓包记录中找到域名为 `stuhtapi.fafu.edu.cn` 的请求。
    4. 查看请求头（Headers）中的 `Authorization` 字段，你会看到一长串字符（如：`MTc3M...`）。
    5. 找一个在线 Base64 解码网站，将这串字符解码。解码后长这样：`1773238142:lnccKsR2ovQ4rbQk:c0a6d234c538193226291c5be73c3461:2_6120909285C95C2DA0CA32C6A2AC76CD`
    6. **提取以 2_ 开头的最后一段**（即 `2_6120909285C95C2DA0CA32C6A2AC76CD`），这就是你的 USER_TOKEN！

4. **配置**

    复制配置文件模板并编辑：
    ```bash
    cp config.json.example config.json
    ```
    然后在 `config.json` 的 "user_token" 配置项填入你的USER_TOKEN。

5. **运行**

    ```bash
    # 使用默认配置文件 (config.json)
    python -m fafu_auto_sign

    # 指定配置文件路径
    python -m fafu_auto_sign --config /path/to/config.json
    # 或简写
    python -m fafu_auto_sign -c /path/to/config.json
    ```

    💡 **建议**：由于本程序自带"心跳保活"机制（每 15 分钟运行一次），建议将其部署在 24 小时开机的云服务器、树莓派或软路由上。在 Linux 下可使用 `nohup` 命令使其在后台持续运行：
    ```bash
    nohup python -m fafu_auto_sign > sign.log 2>&1 &
    ```

### 🔬 技术内幕 (How it works)
对于爱好技术的同学，本脚本的核心难点在于攻破系统的接口安全校验。
API 使用的 Authorization 并非简单的 JWT，而是一种基于时间的动态签名，其逆向还原逻辑如下：
1. 取 URL 的路径部分（剔除 Query 参数）。
2. 生成当前**精确到秒的 Unix 时间戳** (`Timestamp`)。
3. 生成 16位 随机字符串 (`Nonce`)。
4. 通过ADB使电脑连接到手机，安装LSPosed模块Layout Inspect（**需要手机已ROOT**）启用调试浏览器，运用谷歌或Edge浏览器的chrome://inspect功能提取前端JavaScript代码中硬编码的密钥盐值 (`Secret = "AtPs2O1xEnhwkKDV"`)。
5. 将上述参数拼接：`Secret + URL + Timestamp + Nonce`，计算 **MD5** 哈希值作为签名 (Sign)。
6. 最后将 `Timestamp:Nonce:Sign:UserToken` 通过 Base64 编码，生成最终合法的 Header 头部。

此逻辑已在 `generate_auth_header()` 函数中完美用 Python 复现。

### 🤝 参与贡献
欢迎提交 Issue 和 Pull Request！如果你发现了接口变更或开发了新增功能（如引入 Server酱 推送微信通知），非常欢迎一起完善本项目。
1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

### 📄 开源协议 (License)
本项目采用 ***MIT License*** 开源协议。

---

***If you find this project helpful, please give it a ⭐️!***