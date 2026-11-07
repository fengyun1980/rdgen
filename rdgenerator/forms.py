import re

from django import forms
from PIL import Image

# appname/compname are interpolated into single- and double-quoted bash `sed`
# scripts by every generator workflow. These characters corrupt the substitution
# silently or break out of shell quoting (command execution on the runner), and
# CR/LF break sed addressing. Reject them up front with a clear message.
UNSAFE_NAME_CHARS = re.compile(r'[&\\|\'"$`\r\n]')


class GenerateForm(forms.Form):
    #Platform
    platform = forms.ChoiceField(label="平台", choices=[('windows', 'Windows'), ('linux', 'Linux（暂不可用）'), ('android', 'Android'), ('macos', 'macOS')], initial='windows')
    version = forms.ChoiceField(
        label="RustDesk 版本",
        choices=[('master', 'nightly（开发版）'), ('1.3.9', '1.3.9'), ('1.3.8', '1.3.8'), ('1.3.7', '1.3.7'), ('1.3.6', '1.3.6'), ('1.3.5', '1.3.5'), ('1.3.4', '1.3.4'), ('1.3.3', '1.3.3')],
        initial='1.3.9',
        # help_text belongs on the field. As a bare class attribute it never
        # reached form.version.help_text, so the nightly warning never rendered.
        help_text="'master' 是开发版（nightly），包含最新特性，但可能不够稳定",
    )
    delayFix = forms.BooleanField(label="使用第三方 API 时修复连接延迟", initial=True, required=False)

    #General
    exename = forms.CharField(label="EXE 文件名称", required=True)
    appname = forms.CharField(label="自定义应用名称", required=False)
    direction = forms.ChoiceField(label="连接类型", widget=forms.RadioSelect, choices=[
        ('incoming', '仅接受连接（被控）'),
        ('outgoing', '仅发起连接（主控）'),
        ('both', '双向')
    ], initial='both')
    installation = forms.ChoiceField(label="禁用安装", choices=[
        ('installationY', '否，允许安装'),
        ('installationN', '是，禁用安装')
    ], initial='installationY')
    settings = forms.ChoiceField(label="禁用设置", choices=[
        ('settingsY', '否，允许修改设置'),
        ('settingsN', '是，禁用设置')
    ], initial='settingsY')

    #Custom Server
    serverIP = forms.CharField(label="服务器地址（Host）", required=False)
    apiServer = forms.CharField(label="API 服务器", required=False)
    key = forms.CharField(label="密钥（Key）", required=False)
    urlLink = forms.CharField(label="自定义链接地址（替换 https://rustdesk.com）", required=False)
    downloadLink = forms.CharField(label="自定义更新下载地址（替换 https://rustdesk.com/download）", required=False)
    compname = forms.CharField(label="公司名称（用于版权信息）", required=False)

    #Visual
    iconfile = forms.FileField(label="自定义应用图标（.png 格式）", required=False, widget=forms.FileInput(attrs={'accept': 'image/png'}))
    logofile = forms.FileField(label="自定义应用 Logo（.png 格式）", required=False, widget=forms.FileInput(attrs={'accept': 'image/png'}))
    iconbase64 = forms.CharField(required=False)
    logobase64 = forms.CharField(required=False)
    theme = forms.ChoiceField(label="主题", choices=[
        ('light', '浅色'),
        ('dark', '深色'),
        ('system', '跟随系统')
    ], initial='system')
    themeDorO = forms.ChoiceField(label="主题应用方式", choices=[('default', '默认（用户可修改）'), ('override', '强制（不可修改）')], initial='default')

    #Security
    passApproveMode = forms.ChoiceField(label="连接批准方式", choices=[('password', '通过密码接受连接'), ('click', '通过点击接受连接'), ('password-click', '密码或点击均可接受')], initial='password-click')
    permanentPassword = forms.CharField(label="设置固定密码", widget=forms.PasswordInput(), required=False)
    runasadmin = forms.ChoiceField(label="始终以管理员身份运行", choices=[('false', '否'), ('true', '是')], initial='false')
    denyLan = forms.BooleanField(label="禁用局域网发现", initial=False, required=False)
    enableDirectIP = forms.BooleanField(label="启用 IP 直连访问", initial=False, required=False)
    #ipWhitelist = forms.BooleanField(initial=False, required=False)
    autoClose = forms.BooleanField(label="用户无操作时自动断开传入连接", initial=False, required=False)

    #Permissions
    permissionsDorO = forms.ChoiceField(label="权限应用方式", choices=[('default', '默认（用户可修改）'), ('override', '强制（不可修改）')], initial='default')
    permissionsType = forms.ChoiceField(label="权限类型", choices=[('custom', '自定义'), ('full', '完全控制'), ('view', '仅屏幕共享')], initial='custom')
    enableKeyboard = forms.BooleanField(label="启用键盘/鼠标", initial=True, required=False)
    enableClipboard = forms.BooleanField(label="启用剪贴板", initial=True, required=False)
    enableFileTransfer = forms.BooleanField(label="启用文件传输", initial=True, required=False)
    enableAudio = forms.BooleanField(label="启用音频", initial=True, required=False)
    enableTCP = forms.BooleanField(label="启用 TCP 隧道", initial=True, required=False)
    enableRemoteRestart = forms.BooleanField(label="启用远程重启", initial=True, required=False)
    enableRecording = forms.BooleanField(label="启用会话录制", initial=True, required=False)
    enableBlockingInput = forms.BooleanField(label="启用屏蔽用户输入", initial=True, required=False)
    enableRemoteModi = forms.BooleanField(label="启用远程修改配置", initial=False, required=False)

    #Other
    removeWallpaper = forms.BooleanField(label="传入会话时移除壁纸", initial=True, required=False)

    defaultManual = forms.CharField(label="默认设置（手动填写，每行 key = value）", widget=forms.Textarea, required=False)
    overrideManual = forms.CharField(label="强制设置（手动填写，每行 key = value）", widget=forms.Textarea, required=False)

    #custom added features
    cycleMonitor = forms.BooleanField(label="在最小化工具栏添加切换显示器按钮", initial=False, required=False)
    xOffline = forms.BooleanField(label="在地址簿中为离线设备显示 X 标记", initial=False, required=False)
    hidecm = forms.BooleanField(label="允许对远程屏幕隐藏连接窗口", initial=False, required=False)
    removeNewVersionNotif = forms.BooleanField(label="移除新版本通知", initial=False, required=False)

    def clean_exename(self):
        value = self.cleaned_data.get('exename', '')
        # A whitespace-only value sanitises to '' in the view, producing artifacts
        # named ".exe". Reject it here so the user gets actionable feedback.
        if not value.strip():
            raise forms.ValidationError("文件名不能为空。")
        return value

    def _reject_unsafe_name_chars(self, field):
        value = self.cleaned_data.get(field, '')
        if value and UNSAFE_NAME_CHARS.search(value):
            raise forms.ValidationError(
                "包含构建脚本不支持的字符（& \\ | ' \" $ ` 或换行），请移除后重试。"
            )
        return value

    def clean_appname(self):
        return self._reject_unsafe_name_chars('appname')

    def clean_compname(self):
        return self._reject_unsafe_name_chars('compname')

    def clean_iconfile(self):
        image = self.cleaned_data.get('iconfile')
        if image:
            try:
                # Open the image using Pillow
                img = Image.open(image)

                # Check if the image is a PNG (optional, but good practice)
                if img.format != 'PNG':
                    raise forms.ValidationError("仅允许 PNG 格式的图片。")

                # Get image dimensions
                width, height = img.size

                # Check for square dimensions
                if width != height:
                    raise forms.ValidationError("自定义应用图标的尺寸必须为正方形。")

                return image
            except forms.ValidationError:
                raise
            except OSError:  # Handle cases where the uploaded file is not a valid image
                raise forms.ValidationError("无效的图标文件。")
            except Exception as e:  # Catch any other image processing errors
                raise forms.ValidationError(f"处理图标时出错：{e}")

