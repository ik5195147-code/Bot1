# Pyhost

Browser theke Python project (.py ba .zip) upload kore Start / Stop kora, live log dekha ar pip package install korar panel (Flask).

## Railway-te deploy (GitHub theke)
1. GitHub-e ekta notun **private** repo banao (jemon `pyhost`).
2. Ei folder-er sob file repo-te upload koro: Add file > Upload files > Commit changes.
   (`.gitignore` file na dekhale problem nai, skip korte paro.)
3. railway.com > New Project > Deploy from GitHub repo > `pyhost` repo select koro.
4. Service > **Variables** > `HOST_PASSWORD` namey ekta strong password dao.
5. Service > **Settings > Networking > Generate Domain** chapo.
6. Deploy shesh hole domain kholo, password diye login koro.

Deploy Logs-e `Pyhost running` lekha thakle server chalu ache.

### Volume (recommended)
Volume na thakle redeploy ba restart-e upload kora project ar install kora package muche jay.
- Railway project-e ekta Volume banao, service-e connect koro, mount path `/data` dao.
- Pyhost nijei Railway-er `RAILWAY_VOLUME_MOUNT_PATH` bebohar kore, ar kono setting lage na.
- Project-e **Auto-start: on** rakho, tahole redeploy-er por project nijei start hobe.

## Project host kora
1. Panel-e `.py` ba `.zip` upload koro.
2. "File to run" theke main file select kore Save dao (jemon `app.py`).
3. Library lagle "Install packages" box-e lekho, jemon `flask requests protobuf`, tarpor pip install chapo.
   `requirements.txt` thakle "Install requirements" button ashbe.
4. Start chapo. Log niche live dekha jabe. `No module named X` ashle X install koro.

Note: project-er script nijer port nijei choose kore (log-e dekho). Panel script-ke `$PORT` environment variable dey.
Railway-te bairer theke shudhu panel-er port khola, tai project-er nijer web page bairer theke khulbe na.
Shudhu bot/background script cholbe, ba panel-er `/app2/` proxy bebohar koro (niche dekho).

## Settings (environment variables)
| Name | Kaj |
|---|---|
| `HOST_PASSWORD` | Panel-er password. Na dile random password toiri hoye log-e dekhay |
| `PORT` | Panel-er port (Railway nijei dey) |
| `DATA_DIR` | Project, package ar password file rakhar folder (volume thakle auto) |
| `APP2_URL` | `/app2/` kon address-e forward hobe (default `http://127.0.0.1:8080`) |
| `APP2_REQUIRE_LOGIN` | `1` dile `/app2/` dekhte panel login lagbe |

## Termux-e chalano
```
pkg install -y unzip
cd ~ && unzip /storage/emulated/0/Download/pyhost.zip && cd pyhost
bash setup_termux.sh
bash start.sh
```
Prothombar password chaibe. Tarpor browser-e `http://127.0.0.1:8080`.

## Safety
- Panel upload kora code chalay, tai strong password dao ar repo private rakho.
- Login ba token data thaka file (accounts.json, token_cache.json) kauke dekhiyo na.
- `.gitignore` password/secret file GitHub-e jete dey na. Tobu `config.env` ba `.panel_password` kokhono commit koro na.
