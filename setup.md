## 使用 Docker 部署 rdgen 服务

1. 首先在 GitHub 上 Fork 本仓库
2. 接着，创建一个对你的 rdgen 仓库有权限的 GitHub 细粒度访问令牌（fine-grained access token）：
    * 登录你的 GitHub 账号
    * 点击右上角头像，选择 Settings（设置）
    * 在左侧面板底部，点击 Developer Settings（开发者设置）
    * 点击 Personal access tokens（个人访问令牌）
    * 点击 Fine-grained tokens（细粒度令牌）
    * 点击 Generate new token（生成新令牌）
    * 填写令牌名称，按需设置过期时间
    * 在 Repository access（仓库访问权限）下，选择 Only select repositories（仅选定仓库），然后选中你的 rdgen 仓库
    * 为 actions 和 workflows 授予 Read and Write（读写）权限
    * 你可能还需要访问 https://github.com/USERNAME/rdgen/actions 并点击绿色的 Enable Actions 按钮来启用 Actions 功能。
3. 然后登录 GitHub，进入你的 rdgen 仓库页面（https://github.com/USERNAME/rdgen）
   * 点击 Settings（设置）
   * 在左侧面板点击 Secrets and variables，再点击 Actions
   * 点击 New repository secret（新建仓库密钥）
   * Name 填写 GENURL
   * Secret 填写 https://rdgen.hostname.com（或你实际访问该服务时使用的地址）
   * 再次点击 "New repository secret"
   * Name 填写 CALLBACK_TOKEN
   * Secret 填写与你即将写入 docker-compose.yml 的同一个随机值
     （生成方式：```python3 -c 'import secrets; print(secrets.token_urlsafe(32))'```）
     构建流水线在回调 /updategh 和 /save_custom_client 时会以 Bearer 令牌形式发送该值；
     服务端现在会拒绝没有该令牌的回调，因此若不配置，构建虽然能跑完，
     但状态永远不会回传、产物也上传不回来。
4. 下载 docker-compose.yml 文件并填写其中的环境变量：
  * SECRET_KEY="你的密钥" - 运行以下命令生成：```python3 -c 'import secrets; print(secrets.token_urlsafe(64))'```
  * GHUSER="你的 GitHub 用户名"
  * GHBEARER="你的细粒度访问令牌"
  * CALLBACK_TOKEN="一个随机字符串" - 构建回调使用的共享密钥；
    必须与第 3 步新增的 CALLBACK_TOKEN 仓库密钥取值相同。
    生成方式：```python3 -c 'import secrets; print(secrets.token_urlsafe(32))'```
  * ALLOWED_HOSTS="rdgen.yourdomain.com" - 允许的主机名，多个用逗号分隔；
    默认为 "*"，这不安全（伪造的 Host 头可以把构建时的图标/Logo 下载指向攻击者控制的地址）
  * PROTOCOL="https" *可选 - 默认 "https"，如有需要可改为 "http"
  * REPONAME="rdgen" *可选 - 默认 "rdgen"，如果 Fork 时改了仓库名则需相应修改
5. 执行 ```docker compose up -d``` 即可


## 手动部署

1. 一个 GitHub 账号，并 Fork 本仓库
2. 一个对你的 rdgen 仓库有权限的 GitHub 细粒度访问令牌：
    * 登录你的 GitHub 账号
    * 点击右上角头像，选择 Settings（设置）
    * 在左侧面板底部，点击 Developer Settings（开发者设置）
    * 点击 Personal access tokens（个人访问令牌）
    * 点击 Fine-grained tokens（细粒度令牌）
    * 点击 Generate new token（生成新令牌）
    * 填写令牌名称，按需设置过期时间
    * 在 Repository access（仓库访问权限）下，选择 Only select repositories（仅选定仓库），然后选中你的 rdgen 仓库
    * 为 actions 和 workflows 授予 Read and Write（读写）权限
    * 你可能还需要访问 https://github.com/USERNAME/rdgen/actions 并点击绿色的 Enable Actions 按钮来启用 Actions 功能。
3. 配置环境变量与密钥：
    * 运行 rdgen 的服务器上需要设置的环境变量：
        * GHUSER="你的 GitHub 用户名"
        * GHBEARER="你的细粒度访问令牌"
        * SECRET_KEY="一个较长的随机字符串"  *生成方式：```python3 -c 'import secrets; print(secrets.token_urlsafe(64))'```
          （不设置时每次启动都会随机生成新密钥，导致已有会话失效）
        * CALLBACK_TOKEN="一个随机字符串"  *构建回调使用的共享密钥；
          必须与仓库中的 CALLBACK_TOKEN 密钥一致。生成方式：
          ```python3 -c 'import secrets; print(secrets.token_urlsafe(32))'```
        * ALLOWED_HOSTS="rdgen.hostname.com"  *可选 - 允许的主机名，多个用逗号分隔；
          默认为 "*"，这不安全，因为伪造的 Host 头可以把构建时的图标/Logo 下载
          指向攻击者控制的地址
        * DATA_ROOT="/opt/rdgen/data"  *可选 - db.sqlite3、exe/ 和 png/ 的存放位置；
          默认为项目所在目录
        * PROTOCOL="https" *可选 - 默认 "https"，如有需要可改为 "http"
        * REPONAME="rdgen" *可选 - 默认 "rdgen"，如果 Fork 时改了仓库名则需相应修改
        * GHBRANCH="master" *可选 - 默认 "master"；触发构建流水线时所使用的分支
    * GitHub 仓库密钥（在你的 GitHub 账号中为 rdgen 仓库设置）：
        * GENURL="example.com:8000"  *运行 rdgen 的域名和端口，必须能从公网访问；
          根据你的部署方式，端口可能不需要填写
        * CALLBACK_TOKEN  *与上面 CALLBACK_TOKEN 环境变量取值相同的随机字符串；
          构建流水线会把它作为 Bearer 令牌发送给 /updategh 和 /save_custom_client，
          这两个接口现在会拒绝没有该令牌的回调

```
# 进入你想安装 rdgen 的目录（/opt 可换成任意位置）
cd /opt

# 克隆你的 rdgen 仓库，把 bryangerlach 换成你自己的 GitHub 用户名
git clone https://github.com/bryangerlach/rdgen.git

# 进入 rdgen 目录
cd rdgen

# 创建名为 rdgen 的 Python 虚拟环境
python -m venv .venv

# 激活该 Python 虚拟环境
source .venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt

# 初始化数据库
python manage.py migrate

# 启动服务，8000 可换成你想要的端口
python manage.py runserver 0.0.0.0:8000
```

在浏览器中打开 yourdomain:8000

请使用 nginx、caddy、traefik 等工具配置 SSL 反向代理

### 如需开机自启，可以配置一个名为 rdgen.service 的 systemd 服务

按需替换用户、用户组和端口；把 /opt 替换为你实际安装 rdgen 的位置；
将以下内容保存为 /etc/systemd/system/rdgen.service，
并务必修改 GHUSER、GHBEARER、SECRET_KEY 和 CALLBACK_TOKEN

```
[Unit]
Description=Rustdesk Client Generator
[Service]
Type=simple
LimitNOFILE=1000000
Environment="GHUSER=你的GitHub用户名"
Environment="GHBEARER=你的GitHub令牌"
Environment="SECRET_KEY=用secrets_token_urlsafe_64生成"
Environment="CALLBACK_TOKEN=必须与仓库密钥一致"
Environment="ALLOWED_HOSTS=rdgen.yourdomain.com"
PassEnvironment=GHUSER GHBEARER SECRET_KEY CALLBACK_TOKEN ALLOWED_HOSTS
ExecStart=/opt/rdgen/.venv/bin/python3 /opt/rdgen/manage.py runserver 0.0.0.0:8000
WorkingDirectory=/opt/rdgen/
User=root
Group=root
Restart=always
StandardOutput=file:/var/log/rdgen.log
StandardError=file:/var/log/rdgen.error
# 服务崩溃后 10 秒重启
RestartSec=10
[Install]
WantedBy=multi-user.target
```

然后执行以下命令设置开机自启，并手动启动一次：

```
sudo systemctl enable rdgen.service
sudo systemctl start rdgen.service
```

查看服务运行状态：
```
sudo systemctl status rdgen.service
```
