import os
import requests
import json
import subprocess
from pathlib import Path

class MinecraftInstaller:
    def __init__(self, minecraft_version):
        self.minecraft_version = minecraft_version
        self.minecraft_dir = os.path.join(os.getcwd(), 'Minecraft')
        self.versions_dir = os.path.join(self.minecraft_dir, 'versions')
        self.libraries_dir = os.path.join(self.minecraft_dir, 'libraries')
        
        for directory in [self.minecraft_dir, self.versions_dir, self.libraries_dir]:
            os.makedirs(directory, exist_ok=True)

    def download_file(self, url, path):
        # Проверяем существование файла перед загрузкой
        if os.path.exists(path):
            print(f"Файл уже существует: {os.path.basename(path)}")
            return
        
        response = requests.get(url)
        response.raise_for_status()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(response.content)
            print(f"Скачан файл: {os.path.basename(path)}")

    def download_minecraft_client(self, version_data):
        print("Проверка клиента Minecraft...")
        version_dir = os.path.join(self.versions_dir, self.minecraft_version)
        os.makedirs(version_dir, exist_ok=True)

        client_path = os.path.join(version_dir, f"{self.minecraft_version}.jar")
        json_path = os.path.join(version_dir, f"{self.minecraft_version}.json")

        # Проверяем наличие обоих файлов
        if os.path.exists(client_path) and os.path.exists(json_path):
            print(f"Клиент Minecraft {self.minecraft_version} уже установлен")
            return

        print("Скачивание клиента Minecraft...")
        client_url = version_data['downloads']['client']['url']
        self.download_file(client_url, client_path)

        with open(json_path, 'w') as f:
            json.dump(version_data, f)

        print(f"Клиент Minecraft {self.minecraft_version} установлен")

    def download_minecraft_libraries(self):
        print("Скачивание библиотек Minecraft...")
        version_manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest.json").json()
        
        version_url = None
        for version in version_manifest['versions']:
            if version['id'] == self.minecraft_version:
                version_url = version['url']
                break
        
        if not version_url:
            raise Exception(f"Версия {self.minecraft_version} не найдена")
        
        version_data = requests.get(version_url).json()
        
        # Обработка нативных библиотек
        natives_dir = os.path.join(self.minecraft_dir, 'natives')
        os.makedirs(natives_dir, exist_ok=True)
        
        for library in version_data['libraries']:
            # Загрузка обычных библиотек
            if 'downloads' in library and 'artifact' in library['downloads']:
                artifact = library['downloads']['artifact']
                lib_path = os.path.join(self.libraries_dir, artifact['path'])
                self.download_file(artifact['url'], lib_path)
            
            # Загрузка нативных библиотек
            if 'downloads' in library and 'classifiers' in library['downloads']:
                classifiers = library['downloads']['classifiers']
                
                # Определяем какие нативные библиотеки нужны для Windows
                native_keys = [k for k in classifiers.keys() if 'natives-windows' in k]
                
                for native_key in native_keys:
                    native = classifiers[native_key]
                    native_path = os.path.join(natives_dir, os.path.basename(native['path']))
                    self.download_file(native['url'], native_path)
                    
                    # Если это .jar файл, нужно его распаковать
                    if native_path.endswith('.jar'):
                        try:
                            subprocess.run(['jar', 'xf', native_path], cwd=natives_dir, check=True)
                        except subprocess.CalledProcessError:
                            print(f"Предупреждение: Не удалось распаковать {native_path}")
        
        return version_data

    def download_fabric_loader(self):
        print("Скачивание Fabric Loader...")
        fabric_meta = requests.get(f"https://meta.fabricmc.net/v2/versions/loader/{self.minecraft_version}").json()
        loader_version = fabric_meta[0]['loader']['version']
        
        fabric_json_url = f"https://meta.fabricmc.net/v2/versions/loader/{self.minecraft_version}/{loader_version}/profile/json"
        fabric_data = requests.get(fabric_json_url).json()
        
        for library in fabric_data['libraries']:
            if 'url' in library and 'name' in library:
                maven_path = self.convert_maven_path(library['name'])
                lib_url = f"{library['url']}{maven_path}"
                lib_path = os.path.join(self.libraries_dir, maven_path)
                self.download_file(lib_url, lib_path)
                print(f"Скачана Fabric библиотека: {maven_path}")
        
        return loader_version, fabric_data
    def download_fabric_api(self):
        print("Скачивание модов...")
        mods_dir = os.path.join(self.minecraft_dir, 'mods')
        os.makedirs(mods_dir, exist_ok=True)

        # Список модов для скачивания
        mods = {
            "fabric-api": "fabric-api",
            "sodium": "sodium",
            "cloth-config": "cloth-config",
            "entityculling": "entityculling",
            "modmenu": "modmenu",
            "sodium-extra": "sodium-extra",
            "reeses-sodium-options": "reeses-sodium-options"
        }

        for mod_name, mod_id in mods.items():
            print(f"Проверка {mod_name}...")
            mod_path = os.path.join(mods_dir, f"{mod_name}.jar")
            
            if os.path.exists(mod_path):
                print(f"{mod_name} уже установлен")
                continue
                
            print(f"Скачивание {mod_name}...")
            api_versions = requests.get(f"https://api.modrinth.com/v2/project/{mod_id}/version").json()
            
            mod_version = None
            for version in api_versions:
                if self.minecraft_version in version['game_versions'] and 'fabric' in version['loaders']:
                    mod_version = version
                    break
            
            if not mod_version:
                print(f"Предупреждение: {mod_name} не найден для версии {self.minecraft_version}")
                continue
            
            # Берем первый файл из списка (обычно основной файл мода)
            mod_url = mod_version['files'][0]['url']
            self.download_file(mod_url, mod_path)
            print(f"{mod_name} успешно скачан")

    def download_assets(self, version_data):
        print("Проверка ассетов...")
        assets_dir = os.path.join(self.minecraft_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        
        asset_index_path = os.path.join(assets_dir, 'indexes', f"{version_data['assetIndex']['id']}.json")
        
        # Проверяем наличие индекса ассетов
        if not os.path.exists(asset_index_path):
            print("Скачивание индекса ассетов...")
            os.makedirs(os.path.join(assets_dir, 'indexes'), exist_ok=True)
            self.download_file(version_data['assetIndex']['url'], asset_index_path)
        
        with open(asset_index_path, 'r') as f:
            asset_index = json.load(f)
        
        objects_dir = os.path.join(assets_dir, 'objects')
        os.makedirs(objects_dir, exist_ok=True)
        
        missing_assets = False
        for asset_name, asset_info in asset_index['objects'].items():
            hash_value = asset_info['hash']
            hash_prefix = hash_value[:2]
            asset_path = os.path.join(objects_dir, hash_prefix, hash_value)
            
            if not os.path.exists(asset_path):
                missing_assets = True
                asset_url = f"https://resources.download.minecraft.net/{hash_prefix}/{hash_value}"
                self.download_file(asset_url, asset_path)
                print(f"Скачан ассет: {asset_name}")
        
        if not missing_assets:
            print("Все ассеты уже загружены")

    @staticmethod
    def convert_maven_path(maven_name):
        parts = maven_name.split(':')
        group_id = parts[0].replace('.', '/')
        artifact_id = parts[1]
        version = parts[2]
        return f"{group_id}/{artifact_id}/{version}/{artifact_id}-{version}.jar"

    def create_launch_script(self, minecraft_data, fabric_data, loader_version):
        print("Создание скрипта запуска...")
        
        # Создаем log4j2.xml
        print("Создание log4j2.xml...")
        log4j_content = """<?xml version="1.0" encoding="UTF-8"?>
    <Configuration status="WARN" packages="com.mojang.util">
        <Appenders>
            <Console name="SysOut" target="SYSTEM_OUT">
                <PatternLayout pattern="[%d{HH:mm:ss}] [%t/%level]: %msg%n" />
            </Console>
            <Queue name="ServerGuiConsole">
                <PatternLayout pattern="[%d{HH:mm:ss} %level]: %msg%n" />
            </Queue>
            <RollingRandomAccessFile name="File" fileName="logs/latest.log" filePattern="logs/%d{yyyy-MM-dd}-%i.log.gz">
                <PatternLayout pattern="[%d{HH:mm:ss}] [%t/%level]: %msg%n" />
                <Policies>
                    <TimeBasedTriggeringPolicy />
                    <OnStartupTriggeringPolicy />
                </Policies>
            </RollingRandomAccessFile>
        </Appenders>
        <Loggers>
            <Root level="info">
                <filters>
                    <MarkerFilter marker="NETWORK_PACKETS" onMatch="DENY" onMismatch="NEUTRAL" />
                </filters>
                <AppenderRef ref="SysOut"/>
                <AppenderRef ref="File"/>
                <AppenderRef ref="ServerGuiConsole"/>
            </Root>
        </Loggers>
    </Configuration>"""
        
        os.makedirs(os.path.join(self.minecraft_dir, 'assets'), exist_ok=True)
        with open(os.path.join(self.minecraft_dir, 'assets', 'log4j2.xml'), 'w') as f:
            f.write(log4j_content)

        # Формируем classpath
        classpath = []
        
        # Добавляем основной JAR клиента
        client_jar = os.path.join(self.versions_dir, self.minecraft_version, f"{self.minecraft_version}.jar")
        classpath.append(client_jar)

        # Добавляем библиотеки Minecraft
        for library in minecraft_data['libraries']:
            if 'downloads' in library and 'artifact' in library['downloads']:
                lib_path = os.path.join(self.libraries_dir, library['downloads']['artifact']['path'])
                if os.path.exists(lib_path):
                    classpath.append(lib_path)

        # Добавляем библиотеки Fabric
        for library in fabric_data['libraries']:
            if 'name' in library:
                lib_path = os.path.join(self.libraries_dir, self.convert_maven_path(library['name']))
                if os.path.exists(lib_path):
                    classpath.append(lib_path)

        classpath_str = ';'.join(classpath)
        natives_dir = os.path.join(self.minecraft_dir, 'natives')

        # Создаем batch скрипт
        batch_content = f"""@echo off
    set MINECRAFT_DIR=%~dp0Minecraft
    set JAVA_ARGS=-Xmx2G -XX:+UnlockExperimentalVMOptions -XX:+UseG1GC -XX:G1NewSizePercent=20 -XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M

    javaw.exe %JAVA_ARGS% ^
    -Djava.library.path="{natives_dir}" ^
    -Dfabric.loader.game.version={self.minecraft_version} ^
    -Dfabric.loader.version={loader_version} ^
    -Dlog4j.configurationFile="%MINECRAFT_DIR%\\assets\\log4j2.xml" ^
    -Dlog4j2.formatMsgNoLookups=true ^
    -Duser.dir="%MINECRAFT_DIR%" ^
    -cp "{classpath_str}" net.fabricmc.loader.impl.launch.knot.KnotClient ^
    --username Player ^
    --version {self.minecraft_version} ^
    --gameDir "%MINECRAFT_DIR%" ^
    --assetsDir "%MINECRAFT_DIR%\\assets" ^
    --assetIndex {minecraft_data['assetIndex']['id']} ^
    --uuid dummy-uuid ^
    --accessToken dummy-token
    """
        
        # Создаем файл запуска
        with open("start.bat", "w", encoding='utf-8') as f:
            f.write(batch_content)
        
        # Создаем дополнительный скрипт для отладки
        debug_batch_content = batch_content.replace("javaw.exe", "java.exe")
        with open("start_debug.bat", "w", encoding='utf-8') as f:
            f.write(debug_batch_content)
        
        print("Скрипты запуска созданы (start.bat и start_debug.bat)")

def main():
    try:
        subprocess.run(['java', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Ошибка: Java не установлена. Пожалуйста, установите Java и попробуйте снова.")
        return

    minecraft_version = input("Введите версию Minecraft (например, 1.20.1): ")
    
    installer = MinecraftInstaller(minecraft_version)
    try:
        minecraft_data = installer.download_minecraft_libraries()
        installer.download_minecraft_client(minecraft_data)
        installer.download_assets(minecraft_data)
        loader_version, fabric_data = installer.download_fabric_loader()
        installer.download_fabric_api()
        
        installer.create_launch_script(minecraft_data, fabric_data, loader_version)
        
        print("\nУстановка завершена успешно!")
        print("Вы можете запустить игру через start.bat")
    except Exception as e:
        print(f"Ошибка: {str(e)}")

if __name__ == "__main__":
    main()