import io
import logging
from pathlib import Path
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden, Http404, FileResponse
from django.shortcuts import render, get_object_or_404
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
import os
import re
import hmac
import requests
import base64
import json
import uuid
from django.conf import settings as _settings
from .forms import GenerateForm
from .models import GithubRun
from PIL import Image
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Timeout (seconds) for outbound calls to the GitHub API. Without it a stalled
# request blocks a gunicorn worker indefinitely.
GITHUB_TIMEOUT = 30

# /download, /get_png and /save_custom_client build filesystem paths from request
# values. os.path.join discards every earlier component as soon as one is
# absolute, and ".." escapes the intended directory, so both values are checked
# against strict patterns before being used.
_UUID_RE = re.compile(r'^[0-9a-fA-F-]{36}$')
_NAME_RE = re.compile(r'^[\w.@+-]+$')

# Workflow files that /startgh is allowed to dispatch. The platform value used to
# be concatenated straight into the API URL, so it must come from a whitelist.
_ALLOWED_PLATFORMS = ('windows', 'linux', 'android', 'macos')

# Content types for the artifacts the workflows upload back. Serving a .deb or
# .apk as a Microsoft portable-executable is wrong and confuses some browsers.
_DOWNLOAD_CONTENT_TYPES = {
    '.exe': 'application/vnd.microsoft.portable-executable',
    '.msi': 'application/x-msi',
    '.deb': 'application/vnd.debian.binary-package',
    '.rpm': 'application/x-rpm',
    '.zst': 'application/zstd',
    '.apk': 'application/vnd.android.package-archive',
    '.dmg': 'application/x-apple-diskimage',
    '.png': 'image/png',
}


def _safe_parts(uuid_val, filename=None):
    """Return True only when uuid_val is a UUID and filename is a plain name."""
    if not uuid_val or not _UUID_RE.match(uuid_val):
        return False
    if filename is not None:
        if not filename or not _NAME_RE.match(filename) or filename.startswith('.'):
            return False
    return True


def _data_path(subdir, run_uuid, filename):
    """Resolve <DATA_ROOT>/<subdir>/<uuid>/<filename> as an absolute path.

    Previously these were built from bare relative strings ('exe', 'png'), so
    they silently resolved against the process CWD and broke under any launcher
    that does not chdir first. DATA_ROOT lets deployments point at a mounted
    volume so builds survive restarts.
    """
    base = Path(str(_settings.DATA_ROOT))
    return str(base / subdir / run_uuid / filename)


def _data_subdir(subdir, run_uuid):
    """Resolve and create <DATA_ROOT>/<subdir>/<uuid>, returning it as a Path."""
    target = Path(str(_settings.DATA_ROOT)) / subdir / run_uuid
    target.mkdir(parents=True, exist_ok=True)
    return target


def _callback_token_ok(request):
    """Constant-time check of the shared secret used by GitHub Actions callbacks.

    An unset CALLBACK_TOKEN rejects everything rather than falling back to
    accepting anonymous writes, which is what allowed anyone to mark a run as
    successful and have their binary offered for download.
    """
    expected = getattr(_settings, 'CALLBACK_TOKEN', '')
    if not expected:
        logger.error('CALLBACK_TOKEN is not configured; rejecting callback request.')
        return False
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    provided = auth[7:] if auth.startswith('Bearer ') else ''
    return hmac.compare_digest(provided, expected)


def _require_callback_token(request):
    """Return an error response when the callback secret is missing or wrong."""
    if not _callback_token_ok(request):
        return JsonResponse({'error': '需要身份验证'}, status=403)
    return None


def _content_type_for(filename):
    return _DOWNLOAD_CONTENT_TYPES.get(os.path.splitext(filename)[1].lower(),
                                       'application/octet-stream')


def generator_view(request):
    if request.method == 'POST':
        form = GenerateForm(request.POST, request.FILES)
        if form.is_valid():
            platform = form.cleaned_data['platform']
            version = form.cleaned_data['version']
            delayFix = form.cleaned_data['delayFix']
            cycleMonitor = form.cleaned_data['cycleMonitor']
            xOffline = form.cleaned_data['xOffline']
            hidecm = form.cleaned_data['hidecm']
            removeNewVersionNotif = form.cleaned_data['removeNewVersionNotif']
            server = form.cleaned_data['serverIP']
            key = form.cleaned_data['key']
            apiServer = form.cleaned_data['apiServer']
            urlLink = form.cleaned_data['urlLink']
            downloadLink = form.cleaned_data['downloadLink']
            if not server:
                server = 'rs-ny.rustdesk.com' #default rustdesk server
            if not key:
                key = 'OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw=' #default rustdesk key
            if not apiServer:
                apiServer = server+":21114"
            if not urlLink:
                urlLink = "https://rustdesk.com"
            if not downloadLink:
                downloadLink = "https://rustdesk.com/download"
            direction = form.cleaned_data['direction']
            installation = form.cleaned_data['installation']
            settings = form.cleaned_data['settings']
            appname = form.cleaned_data['appname']
            filename = form.cleaned_data['exename']
            compname = form.cleaned_data['compname']
            if not compname:
                compname = "Purslane Ltd"
            permPass = form.cleaned_data['permanentPassword']
            theme = form.cleaned_data['theme']
            themeDorO = form.cleaned_data['themeDorO']
            runasadmin = form.cleaned_data['runasadmin']
            passApproveMode = form.cleaned_data['passApproveMode']
            denyLan = form.cleaned_data['denyLan']
            enableDirectIP = form.cleaned_data['enableDirectIP']
            #ipWhitelist = form.cleaned_data['ipWhitelist']
            autoClose = form.cleaned_data['autoClose']
            permissionsDorO = form.cleaned_data['permissionsDorO']
            permissionsType = form.cleaned_data['permissionsType']
            enableKeyboard = form.cleaned_data['enableKeyboard']
            enableClipboard = form.cleaned_data['enableClipboard']
            enableFileTransfer = form.cleaned_data['enableFileTransfer']
            enableAudio = form.cleaned_data['enableAudio']
            enableTCP = form.cleaned_data['enableTCP']
            enableRemoteRestart = form.cleaned_data['enableRemoteRestart']
            enableRecording = form.cleaned_data['enableRecording']
            enableBlockingInput = form.cleaned_data['enableBlockingInput']
            enableRemoteModi = form.cleaned_data['enableRemoteModi']
            removeWallpaper = form.cleaned_data['removeWallpaper']
            defaultManual = form.cleaned_data['defaultManual']
            overrideManual = form.cleaned_data['overrideManual']

            if all(char.isascii() for char in filename):
                filename = re.sub(r'[^\w\s-]', '_', filename).strip()
                filename = filename.replace(" ","_")
            else:
                filename = "rustdesk"
            # A whitespace-only exename sanitises to '' (strip() runs after the
            # substitution), which then produces artifacts named ".exe" that
            # /download cannot resolve. Fall back to the default instead.
            if not filename:
                filename = "rustdesk"
            if not all(char.isascii() for char in appname):
                appname = "rustdesk"
            myuuid = str(uuid.uuid4())
            protocol = _settings.PROTOCOL
            # GENURL is the operator-declared public address and is not attacker
            # controlled. request.get_host() is only a fallback: with
            # ALLOWED_HOSTS=['*'] a forged Host header would otherwise point the
            # build runners at an attacker-controlled URL for icon/logo download.
            if _settings.GENURL:
                genurl = _settings.GENURL
                if '://' not in genurl:
                    genurl = f"{protocol}://{genurl}"
                full_url = genurl.rstrip('/')
            else:
                full_url = f"{protocol}://{request.get_host()}"
            # save_png() returns None when there is nothing to save or the data
            # is invalid. The workflow guard is `iconlink != 'false'`, so None
            # would wrongly enter the icon step, move the stock icons aside and
            # then fail on fromJson(null). Normalise to the string "false".
            iconlink = "false"
            try:
                iconfile = form.cleaned_data.get('iconfile')
                if not iconfile:
                    iconfile = form.cleaned_data.get('iconbase64')
                if iconfile:
                    saved = save_png(iconfile, myuuid, full_url, "icon.png")
                    if saved:
                        iconlink = saved
            except Exception:
                logger.exception("failed to get icon, using default")
            logolink = "false"
            try:
                logofile = form.cleaned_data.get('logofile')
                if not logofile:
                    logofile = form.cleaned_data.get('logobase64')
                if logofile:
                    saved = save_png(logofile, myuuid, full_url, "logo.png")
                    if saved:
                        logolink = saved
            except Exception:
                logger.exception("failed to get logo, using default")

            ###create the custom.txt json here and send in as inputs below
            decodedCustom = {}
            # The form emits lowercase 'both'; comparing against 'Both' was always
            # True, so conn-type was written even for bidirectional. RustDesk's
            # read_custom_client only understands incoming/outgoing.
            if direction in ("incoming", "outgoing"):
                decodedCustom['conn-type'] = direction
            if installation == "installationN":
                decodedCustom['disable-installation'] = 'Y'
            if settings == "settingsN":
                decodedCustom['disable-settings'] = 'Y'
            # .upper are method objects; the old `appname.upper != "rustdesk".upper`
            # compared two bound methods and was always True. Call them.
            if appname.upper() != "RUSTDESK" and appname != "":
                decodedCustom['app-name'] = appname
            decodedCustom['override-settings'] = {}
            decodedCustom['default-settings'] = {}
            if permPass != "":
                decodedCustom['password'] = permPass
            if theme != "system":
                if themeDorO == "default":
                    decodedCustom['default-settings']['theme'] = theme
                elif themeDorO == "override":
                    decodedCustom['override-settings']['theme'] = theme
            decodedCustom['approve-mode'] = passApproveMode
            decodedCustom['enable-lan-discovery'] = 'N' if denyLan else 'Y'
            decodedCustom['direct-server'] = 'Y' if enableDirectIP else 'N'
            decodedCustom['allow-auto-disconnect'] = 'Y' if autoClose else 'N'
            decodedCustom['allow-remove-wallpaper'] = 'Y' if removeWallpaper else 'N'
            if permissionsDorO == "default":
                decodedCustom['default-settings']['access-mode'] = permissionsType
                decodedCustom['default-settings']['enable-keyboard'] = 'Y' if enableKeyboard else 'N'
                decodedCustom['default-settings']['enable-clipboard'] = 'Y' if enableClipboard else 'N'
                decodedCustom['default-settings']['enable-file-transfer'] = 'Y' if enableFileTransfer else 'N'
                decodedCustom['default-settings']['enable-audio'] = 'Y' if enableAudio else 'N'
                decodedCustom['default-settings']['enable-tunnel'] = 'Y' if enableTCP else 'N'
                decodedCustom['default-settings']['enable-remote-restart'] = 'Y' if enableRemoteRestart else 'N'
                decodedCustom['default-settings']['enable-record-session'] = 'Y' if enableRecording else 'N'
                decodedCustom['default-settings']['enable-block-input'] = 'Y' if enableBlockingInput else 'N'
                decodedCustom['default-settings']['allow-remote-config-modification'] = 'Y' if enableRemoteModi else 'N'
            else:
                decodedCustom['override-settings']['access-mode'] = permissionsType
                decodedCustom['override-settings']['enable-keyboard'] = 'Y' if enableKeyboard else 'N'
                decodedCustom['override-settings']['enable-clipboard'] = 'Y' if enableClipboard else 'N'
                decodedCustom['override-settings']['enable-file-transfer'] = 'Y' if enableFileTransfer else 'N'
                decodedCustom['override-settings']['enable-audio'] = 'Y' if enableAudio else 'N'
                decodedCustom['override-settings']['enable-tunnel'] = 'Y' if enableTCP else 'N'
                decodedCustom['override-settings']['enable-remote-restart'] = 'Y' if enableRemoteRestart else 'N'
                decodedCustom['override-settings']['enable-record-session'] = 'Y' if enableRecording else 'N'
                decodedCustom['override-settings']['enable-block-input'] = 'Y' if enableBlockingInput else 'N'
                decodedCustom['override-settings']['allow-remote-config-modification'] = 'Y' if enableRemoteModi else 'N'

            # Manual settings are free-form textarea input. Blank lines (a double
            # Enter) and values containing '=' both used to raise ValueError from
            # the two-element unpack, after form.is_valid() and outside any try,
            # turning a user typo into a 500. Split once and skip malformed lines.
            def _apply_manual(target, text):
                for line in (text or '').splitlines():
                    if '=' not in line:
                        continue
                    k, value = line.split('=', 1)
                    k = k.strip()
                    if k:
                        target[k] = value.strip()

            _apply_manual(decodedCustom['default-settings'], defaultManual)
            _apply_manual(decodedCustom['override-settings'], overrideManual)

            decodedCustomJson = json.dumps(decodedCustom)

            string_bytes = decodedCustomJson.encode("ascii")
            base64_bytes = base64.b64encode(string_bytes)
            encodedCustom = base64_bytes.decode("ascii")

            #github limits inputs to 10, so lump extras into one with json
            extras = {}
            extras['genurl'] = _settings.GENURL
            extras['runasadmin'] = runasadmin
            extras['urlLink'] = urlLink
            extras['downloadLink'] = downloadLink
            extras['delayFix'] = 'true' if delayFix else 'false'
            extras['version'] = version
            extras['rdgen'] = 'true'
            extras['cycleMonitor'] = 'true' if cycleMonitor else 'false'
            extras['xOffline'] = 'true' if xOffline else 'false'
            extras['hidecm'] = 'true' if hidecm else 'false'
            extras['removeNewVersionNotif'] = 'true' if removeNewVersionNotif else 'false'
            extras['compname'] = compname
            # The workflows authenticate their /save_custom_client callback using
            # the CALLBACK_TOKEN repository secret directly. It is deliberately
            # NOT passed through `extras`: workflow_dispatch inputs are visible
            # on the run page to anyone with repo read access.
            extra_input = json.dumps(extras)

            ####from here run the github action, we need user, repo, access token.
            if platform == 'windows':
                url = 'https://api.github.com/repos/'+_settings.GHUSER+'/'+_settings.REPONAME+'/actions/workflows/generator-windows.yml/dispatches' 
            elif platform == 'linux':
                url = 'https://api.github.com/repos/'+_settings.GHUSER+'/'+_settings.REPONAME+'/actions/workflows/generator-linux.yml/dispatches'  
            elif platform == 'android':
                url = 'https://api.github.com/repos/'+_settings.GHUSER+'/'+_settings.REPONAME+'/actions/workflows/generator-android.yml/dispatches'
            elif platform == 'macos':
                url = 'https://api.github.com/repos/'+_settings.GHUSER+'/'+_settings.REPONAME+'/actions/workflows/generator-macos.yml/dispatches'
            else:
                url = 'https://api.github.com/repos/'+_settings.GHUSER+'/'+_settings.REPONAME+'/actions/workflows/generator-windows.yml/dispatches'

            data = {
                "ref":_settings.GHBRANCH,
                "inputs":{
                    "server":server,
                    "key":key,
                    "apiServer":apiServer,
                    "custom":encodedCustom,
                    "uuid":myuuid,
                    "iconlink":iconlink,
                    "logolink":logolink,
                    "appname":appname,
                    "extras":extra_input,
                    "filename":filename
                }
            } 
            headers = {
                'Accept':  'application/vnd.github+json',
                'Content-Type': 'application/json',
                'Authorization': 'Bearer '+_settings.GHBEARER,
                'X-GitHub-Api-Version': '2022-11-28'
            }
            # Register the run first so the waiting page has a row to poll, then
            # dispatch. The outbound call gets a timeout so a stalled GitHub API
            # cannot pin a worker forever.
            create_github_run(myuuid)
            try:
                response = requests.post(url, json=data, headers=headers, timeout=GITHUB_TIMEOUT)
            except requests.RequestException as exc:
                logger.exception("GitHub dispatch request failed")
                GithubRun.objects.filter(uuid=myuuid).update(status="Failed to start generator")
                return JsonResponse({"error": "无法连接到 GitHub，构建启动失败"}, status=502)
            logger.info("GitHub dispatch for %s returned %s", myuuid, response.status_code)
            if response.status_code == 204:
                return render(request, 'waiting.html', {'filename':filename, 'uuid':myuuid, 'status':"正在启动生成器……请稍候", 'platform':platform})
            else:
                # Mark the run failed so the polling page stops looping, and return
                # a real error status instead of a 200 with an error body.
                GithubRun.objects.filter(uuid=myuuid).update(status="Failed to start generator")
                logger.error("GitHub rejected dispatch (%s): %s", response.status_code, response.text[:500])
                return JsonResponse({"error": "GitHub 拒绝了构建请求"}, status=502)
    else:
        form = GenerateForm()
    #return render(request, 'maintenance.html')
    return render(request, 'generator.html', {'form': form})


@require_GET
def check_for_file(request):
    filename = request.GET.get('filename', '')
    run_uuid = request.GET.get('uuid', '')
    platform = request.GET.get('platform', '')
    if not _safe_parts(run_uuid, filename or None):
        raise Http404("无效的请求")

    # .first() returned None for an unknown uuid and the next line dereferenced
    # it -> AttributeError 500. waiting.html re-navigates here every 5 seconds,
    # so the browser sat in an error loop.
    gh_run = get_object_or_404(GithubRun, uuid=run_uuid)
    status = gh_run.status

    if (status or "").lower() == "success":
        return render(request, 'generated.html', {'filename': filename, 'uuid': run_uuid, 'platform': platform})
    return render(request, 'waiting.html', {'filename': filename, 'uuid': run_uuid, 'status': status, 'platform': platform})


def _serve_file(base_dir, request, allowed_suffixes=None):
    """Validate the request params and stream the file from base_dir/<uuid>/<name>."""
    filename = request.GET.get('filename', '')
    run_uuid = request.GET.get('uuid', '')
    if not _safe_parts(run_uuid, filename):
        return HttpResponseForbidden("无效的文件名")
    if allowed_suffixes and not filename.lower().endswith(allowed_suffixes):
        return HttpResponseForbidden("无效的文件名")

    file_path = _data_path(base_dir, run_uuid, filename)
    if not os.path.isfile(file_path):
        # Used to be an uncaught FileNotFoundError -> 500 when the user clicked
        # a package the workflow never produced.
        raise Http404("文件不存在")

    # FileResponse streams instead of buffering a 20-40 MB artifact into RAM,
    # which HttpResponse(file) did (it materialises the whole file eagerly).
    response = FileResponse(open(file_path, 'rb'), as_attachment=False,
                            content_type=_content_type_for(filename))
    ascii_name = filename.encode('ascii', 'ignore').decode('ascii') or 'download'
    response['Content-Disposition'] = (
        f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'
    )
    return response


@require_GET
def download(request):
    return _serve_file('exe', request)


@require_GET
def get_png(request):
    # Called by the build runners to fetch the user-supplied icon/logo.
    return _serve_file('png', request, allowed_suffixes=('.png',))


def create_github_run(myuuid):
    """Internal helper: register a run row before dispatching to GitHub."""
    GithubRun.objects.update_or_create(
        uuid=myuuid,
        defaults={'status': "正在启动生成器……请稍候"},
    )


@csrf_exempt
@require_POST
def create_github_run_view(request):
    """HTTP endpoint for /creategh.

    urls.py used to route this path straight at create_github_run(myuuid), so
    Django passed the HttpRequest as the uuid and stored its repr() in the
    database -- from an unauthenticated route, no less.
    """
    denied = _require_callback_token(request)
    if denied:
        return denied
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': '无效的 JSON 数据'}, status=400)
    myuuid = data.get('uuid', '')
    if not _safe_parts(myuuid):
        return JsonResponse({'error': '无效的任务标识'}, status=400)
    create_github_run(myuuid)
    return JsonResponse({'status': 'created', 'uuid': myuuid})


@csrf_exempt
@require_POST
def update_github_run(request):
    """Status callback from GitHub Actions. Requires the shared secret.

    Previously anonymous, so anyone could mark an arbitrary uuid as "Success".
    Combined with the unauthenticated /save_custom_client upload that let an
    attacker plant a binary and have this site serve it as an official build.
    """
    denied = _require_callback_token(request)
    if denied:
        return denied
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': '无效的 JSON 数据'}, status=400)

    myuuid = data.get('uuid')
    mystatus = data.get('status')
    if not _safe_parts(myuuid):
        return JsonResponse({'error': '无效的任务标识'}, status=400)
    if not isinstance(mystatus, str) or len(mystatus) > 100:
        return JsonResponse({'error': '无效的状态值'}, status=400)

    GithubRun.objects.filter(uuid=myuuid).update(status=mystatus)
    return HttpResponse('')

def resize_and_encode_icon(imagefile):
    maxWidth = 200
    try:
        with io.BytesIO() as image_buffer:
            for chunk in imagefile.chunks():
                image_buffer.write(chunk)
            image_buffer.seek(0)

            img = Image.open(image_buffer)
            imgcopy = img.copy()
    except (IOError, OSError):
        raise ValueError("Uploaded file is not a valid image format.")

    # Check if resizing is necessary
    if img.size[0] <= maxWidth:
        with io.BytesIO() as image_buffer:
            imgcopy.save(image_buffer, format=imagefile.content_type.split('/')[1])
            image_buffer.seek(0)
            return_image = ContentFile(image_buffer.read(), name=imagefile.name)
        return base64.b64encode(return_image.read())

    # Calculate resized height based on aspect ratio
    wpercent = (maxWidth / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))

    # Resize the image while maintaining aspect ratio using LANCZOS resampling
    imgcopy = imgcopy.resize((maxWidth, hsize), Image.Resampling.LANCZOS)

    with io.BytesIO() as resized_image_buffer:
        imgcopy.save(resized_image_buffer, format=imagefile.content_type.split('/')[1])
        resized_image_buffer.seek(0)

        resized_imagefile = ContentFile(resized_image_buffer.read(), name=imagefile.name)

    # Return the Base64 encoded representation of the resized image
    resized64 = base64.b64encode(resized_imagefile.read())
    #print(resized64)
    return resized64
 
#the following is used when accessed from an external source, like the rustdesk api server
@csrf_exempt
@require_POST
def startgh(request):
    """Dispatch a build on behalf of an external caller (e.g. the RustDesk API server).

    Was anonymous and concatenated data_.get('platform') straight into the GitHub
    URL, so anyone could burn Actions minutes and steer the workflow path. Now it
    requires the shared secret and the platform must be whitelisted.
    """
    denied = _require_callback_token(request)
    if denied:
        return denied
    try:
        data_ = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': '无效的 JSON 数据'}, status=400)

    platform = data_.get('platform')
    if platform not in _ALLOWED_PLATFORMS:
        return JsonResponse({'error': '不支持的平台'}, status=400)
    run_uuid = data_.get('uuid')
    if not _safe_parts(run_uuid):
        return JsonResponse({'error': '无效的任务标识'}, status=400)

    ####from here run the github action, we need user, repo, access token.
    url = 'https://api.github.com/repos/'+_settings.GHUSER+'/'+_settings.REPONAME+'/actions/workflows/generator-'+platform+'.yml/dispatches'
    data = {
        "ref":_settings.GHBRANCH,
        "inputs":{
            "server":data_.get('server'),
            "key":data_.get('key'),
            "apiServer":data_.get('apiServer'),
            "custom":data_.get('custom'),
            "uuid":run_uuid,
            "iconlink":data_.get('iconlink'),
            "logolink":data_.get('logolink'),
            "appname":data_.get('appname'),
            "extras":data_.get('extras'),
            "filename":data_.get('filename')
        }
    }
    headers = {
        'Accept':  'application/vnd.github+json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer '+_settings.GHBEARER,
        'X-GitHub-Api-Version': '2022-11-28'
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=GITHUB_TIMEOUT)
    except requests.RequestException:
        logger.exception("startgh dispatch failed")
        return JsonResponse({'error': '无法连接到 GitHub'}, status=502)
    logger.info("startgh dispatch for %s returned %s", run_uuid, response.status_code)
    return HttpResponse(status=204)

def save_png(file, uuid, domain, name):
    # uuid/name are internal here, but validate anyway so a future caller cannot
    # turn them into a path escape.
    if not _safe_parts(uuid, name):
        logger.error("save_png called with unsafe uuid/name: %r/%r", uuid, name)
        return None

    png_dir = _data_subdir("png", uuid)
    file_save_path = str(png_dir / name)

    if isinstance(file, str):  # Check if it's a base64 string
        try:
            header, encoded = file.split(';base64,')
            decoded_img = base64.b64decode(encoded)
            file = ContentFile(decoded_img, name=name) # Create a file-like object
        except ValueError:
            logger.warning("Invalid base64 data for %s", name)
            return None  # Or handle the error as you see fit
        except Exception as e:  # Catch general exceptions during decoding
            logger.warning("Error decoding base64 for %s: %s", name, e)
            return None

    with open(file_save_path, "wb+") as f:
        for chunk in file.chunks():
            f.write(chunk)
    imageJson = {}
    imageJson['url'] = domain
    imageJson['uuid'] = uuid
    imageJson['file'] = name
    #return "%s/%s" % (domain, file_save_path)
    return json.dumps(imageJson)

@csrf_exempt
@require_POST
def save_custom_client(request):
    """Receive a finished artifact from a GitHub Actions runner.

    Was anonymous and built the path from request-controlled uuid + file.name,
    allowing directory traversal writes. Now requires the shared secret and
    validates both parts.
    """
    denied = _require_callback_token(request)
    if denied:
        return denied
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': '缺少文件'}, status=400)
    myuuid = request.POST.get('uuid')
    if not _safe_parts(myuuid, file.name):
        return HttpResponseForbidden("无效的文件名")
    exe_dir = _data_subdir("exe", myuuid)
    file_save_path = str(exe_dir / file.name)
    with open(file_save_path, "wb+") as f:
        for chunk in file.chunks():
            f.write(chunk)

    return HttpResponse("File saved successfully!")