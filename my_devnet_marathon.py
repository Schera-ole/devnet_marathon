import datetime as dt
import csv
import logging
from netmiko import ConnectHandler
import os
import textfsm

path_to_devices = 'devices.csv'
path_to_backup = 'backup/'
devices = []
template_cdp_neigh = r'S:\python-different\ntc-templates\templates\cisco_ios_show_cdp_neighbors.textfsm'
template_sh_ver = r'S:\python-different\ntc-templates\templates\cisco_ios_show_version.textfsm'
ntp_server='10.10.10.10'


def backup_folder(path_to_backup):
    #Проверяем наличие папки под бэкап
    return True if os.path.exists(path_to_backup) else False
        

def enable_logging():
    logging.basicConfig(filename='netmiko.log', level=logging.DEBUG)
    logger = logging.getLogger("netmiko")


def get_devices_from_file(devices_file):
    #Получаем список оборудования
    with open(devices_file,'r') as scroll:
        reader = csv.DictReader(scroll)
        for row in reader:
            devices.append(row)
        return devices


def get_time():
    #Получаем метку времени
    now = dt.datetime.now()
    return now.strftime("%Y_%m_%d-%H_%M_%S")
    

def cdp_handling(ssh):
    #Обработка cdp
    request = ssh.send_command('sh cdp neigh')
    if 'CDP is not enabled' not in request:
        with open(template_cdp_neigh) as template:
            fsm = textfsm.TextFSM(template)
            result = fsm.ParseText(request)
        return 'CDP is On, '+str(len(result))+' peers'
    else:
        return 'CDP is Off'


def ntp_handling(ssh):
    #Обработка ntp
    ssh.send_config_set('clock timezone UTC 0 0')
    request = ssh.send_command('sh ntp status')
    if 'Clock is synchronized' in request:
        return 'Clock is synchronized'
    else:
        request = ssh.send_command(f'ping {ntp_server}')
        if '!!!!' in request:
            ssh.send_config_set(f'ntp server {ntp_server}')
            return 'New ntp server set. Check synchronized'
        else:
            print('К сожалению, ntp сервер недоступен')
            return 'Clock is unsynchronized'


def version_handling(ssh):
    #Обработка sh ver
    request = ssh.send_command('sh ver')
    with open(template_sh_ver) as template:
        fsm = textfsm.TextFSM(template)
        result = fsm.ParseText(request)
        return result[0]


def connect_to_device(device, path_to_backup):
    #Тестовые машины были с авторизацией сразу в решётку, поэтому без secret
    device_params = {
        'device_type': device['device_type'],
        'ip': device['ip'],
        'username': device['username'],
        'password': device['password'],
    }
    with ConnectHandler(**device_params) as ssh:
        prompt = ssh.find_prompt()
        timestamp = get_time()
        filename = prompt.rstrip('>,#')+'_'+timestamp
        request = ssh.send_command('sh run')
        with open(f'{path_to_backup}{filename}', 'w') as f:
            f.write(request)
        version_result = version_handling(ssh)
        cdp_result = cdp_handling(ssh)
        ntp_result = ntp_handling(ssh)
        if device['layer'] == 'router':
            if 'npe' in version_result[-5]:
                npe_result = 'NPE'
            else:
                npe_result = 'PE'
        else:
            npe_result = 'inapplicable'
        result = f'{version_result[2]}|{version_result[-4][0]}|{version_result[0]}|{npe_result}|{cdp_result}|{ntp_result}'
        return result
        

def main():
    enable_logging()
    devices = get_devices_from_file(path_to_devices)
    if not backup_folder(path_to_backup):
        os.mkdir(path_to_backup)
    for unit in devices:
        try:
            total = connect_to_device(unit, path_to_backup)
            print(total)
        except:
            print(f'Произошла ошибка при подключении к {unit["device"]}')
            continue


if __name__ == "__main__":
    main()
