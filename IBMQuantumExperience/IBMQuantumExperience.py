'''
    IBM Quantum Experience Python API Client
'''
import json
import datetime
import time
import requests


class _Credentials(object):

    config_base = {
        'url': 'https://quantumexperience.ng.bluemix.net/api'
    }

    def __init__(self, token, config=None):
        self.token_unique = token
        if config and config.get('url', None):
            self.config = config
        else:
            self.config = self.config_base

        self.data_credentials = {}
        self.obtain_token()

    def obtain_token(self):
        '''
        Obtain the token to access to QX Platform
        '''
        self.data_credentials = requests.post(str(self.config.get('url') +
                                                  "/users/loginWithToken"),
                                              data={'apiToken':
                                                    self.token_unique}).json()

        if not self.get_token():
            print('ERROR: Not token valid')

    def get_token(self):
        '''
        Get Authenticated Token to connect with QX Platform
        '''
        return self.data_credentials.get('id', None)

    def get_user_id(self):
        '''
        Get User Id in QX Platform
        '''
        return self.data_credentials.get('userId', None)

    def get_config(self):
        '''
        Get Configuration setted to connect with QX Platform
        '''
        return self.config


class _Request(object):

    def __init__(self, token, config=None):
        self.credential = _Credentials(token, config)

    def check_token(self, respond):
        '''
        Check is the user's token is valid
        '''
        if respond.status_code == 401:
            self.credential.obtain_token()
            return False
        return True

    def post(self, path, params='', data=None):
        '''
        POST Method Wrapper of the REST API
        '''
        if data is None:
            data = {}
        headers = {'Content-Type': 'application/json'}
        respond = requests.post(
            str(self.credential.config['url'] + path + '?access_token=' +
                self.credential.get_token() + params),
            data=data,
            headers=headers)
        if not self.check_token(respond):
            respond = requests.post(
                str(self.credential.config['url'] + path + '?access_token=' +
                    self.credential.get_token() + params),
                data=data, headers=headers)
        return respond.json()

    def get(self, path, params='', with_token=True):
        '''
        GET Method Wrapper of the REST API
        '''
        if with_token:
            access_token = self.credential.get_token()
            if access_token:
                access_token = '?access_token=' + str(access_token)
            else:
                access_token = ''
        else:
            access_token = ''
        respond = requests.get(
            self.credential.config['url'] + path + access_token + params)
        if not self.check_token(respond):
            respond = requests.get(
                self.credential.config['url'] + path + access_token + params)
        return respond.json()


class IBMQuantumExperience(object):
    '''
    The Connector Class to do request to QX Platform
    '''
    __names_device_ibmqxv2 = ['ibmqx5qv2', 'ibmqx2', 'qx5qv2', 'qx5q', 'real']
    __names_device_ibmqxv3 = ['ibmqx3']
    __names_device_simulator = ['simulator', 'sim_trivial_2',
                                'ibmqx_qasm_simulator']

    def __init__(self, token, config=None):
        self.req = _Request(token, config)

    def _check_device(self, device, endpoint):
        '''
        Check if the name of a device is valid to run in QX Platform
        '''
        device = device.lower()
        if endpoint == 'experiment':
            if device in self.__names_device_ibmqxv2:
                return 'real'
            elif device in self.__names_device_ibmqxv3:
                return 'ibmqx3'
            elif device in self.__names_device_simulator:
                return 'sim_trivial_2'
        elif endpoint == 'job':
            if device in self.__names_device_ibmqxv2:
                return 'real'
            elif device in self.__names_device_ibmqxv3:
                return 'ibmqx3'
            elif device in self.__names_device_simulator:
                return 'simulator'
        elif endpoint == 'status':
            if device in self.__names_device_ibmqxv2:
                return 'chip_real'
            elif device in self.__names_device_ibmqxv3:
                return 'ibmqx3'
            elif device in self.__names_device_simulator:
                return 'chip_simulator'
        elif endpoint == 'calibration':
            if device in self.__names_device_ibmqxv2:
                return 'Real5Qv2'
            elif device in self.__names_device_ibmqxv3:
                return 'ibmqx3'
        return None

    def _check_credentials(self):
        '''
        Check if the user has permission in QX platform
        '''
        if not self.req.credential.get_token():
            return False
        return True

    def _beautify_calibration_parameters(self, cals, device):
        '''
        Beautify the calibrations returned by QX platform
        '''
        ret = {}
        ret['name'] = device
        calibration_date = None
        units = {}
        for key in cals:
            if key == 'fridge_temperature':
                for attr in cals[key]:
                    if 'value' in attr:
                        ret['fridgeTemperature'] = float(attr['value'])
                        unit = attr['units']
                        if unit == 'Kelvin':
                            unit = "K"
                        units['fridgeTemperature'] = unit
                    if 'date' in attr:
                        calibration_date = str(attr['date'])
            elif key.startswith('Q'):
                new_key = 'Q' + str(int(key.replace('Q', '')) - 1)
                ret[new_key] = {}
                for attr in cals[key]:
                    if 'label' in attr:
                        if attr['label'].startswith("f") and 'value' in attr:
                            ret[new_key]['frequency'] = float(attr['value'])
                            units['frequency'] = str(attr['units'])
                        if attr['label'].startswith("t_1") and 'value' in attr:
                            ret[new_key]['t1'] = float(attr['value'])
                            unit = attr['units']
                            if unit == 'microseconds':
                                unit = "us"
                            units['tx'] = unit
                        if attr['label'].startswith("t_2") and 'value' in attr:
                            ret[new_key]['t2'] = float(attr['value'])
                            unit = attr['units']
                            if unit == 'microseconds':
                                unit = "us"
                            units['tx'] = unit
                    if not calibration_date and 'date' in attr:
                        calibration_date = attr['date']

        if calibration_date:
            ret['coherenceStartTime'] = calibration_date

        # TODO: Get from new calibrations files
        ret['singleQubitGateTime'] = 80
        ret['units'] = units

        return {"backend": ret}

    def _beautify_calibration(self, cals, device):
        '''
        Beautify the calibrations returned by QX platform
        '''
        ret = {}
        ret['name'] = device
        calibration_date = None
        coupling_map = {}
        for key in cals:
            if key.startswith('CR'):
                qubits = key.replace('CR', '').split('_')
                qubit_from = int(qubits[0])-1
                qubit_to = int(qubits[1])-1
                key_qubit = str(qubit_from)
                if key_qubit not in coupling_map:
                    coupling_map[key_qubit] = []
                coupling_map[key_qubit].append(qubit_to)
                new_key = 'CX' + str(qubit_from) + "_" + str(qubit_to)
                ret[new_key] = {}
                for attr in cals[key]:
                    if 'label' in attr:
                        if attr['label'].startswith("e_g") and 'value' in attr:
                            ret[new_key]['gateError'] = float(attr['value'])
                    if not calibration_date and 'date' in attr:
                        calibration_date = str(attr['date'])
            elif key.startswith('Q'):
                new_key = 'Q' + str(int(key.replace('Q', ''))-1)
                ret[new_key] = {}
                for attr in cals[key]:
                    if 'label' in attr:
                        if attr['label'].startswith("e_g") and 'value' in attr:
                            ret[new_key]['gateError'] = float(attr['value'])
                        if attr['label'].startswith("e_r") and 'value' in attr:
                            ret[new_key]['readoutError'] = float(attr['value'])
                    if not calibration_date and 'date' in attr:
                        calibration_date = str(attr['date'])

        if calibration_date:
            ret['calibrationStartTime'] = calibration_date

        if coupling_map:
            ret['couplingMap'] = coupling_map

        return {"backend": ret}

    def get_execution(self, id_execution):
        '''
        Get a execution, by its id
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        execution = self.req.get('/Executions/' + id_execution, '')
        if execution["codeId"]:
            execution['code'] = self.get_code(execution["codeId"])
        return execution

    def get_result_from_execution(self, id_execution):
        '''
        Get the result of a execution, byt the execution id
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        execution = self.req.get('/Executions/' + id_execution, '')
        result = {}
        if "result" in execution and "data" in execution["result"]:
            if execution["result"]["data"].get('p', None):
                result["measure"] = execution["result"]["data"]["p"]
            if execution["result"]["data"].get('valsxyz', None):
                result["bloch"] = execution["result"]["data"]["valsxyz"]
            if "additionalData" in execution["result"]["data"]:
                result["extraInfo"] = execution["result"]["data"]["additionalData"]

        return result

    def get_code(self, id_code):
        '''
        Get a code, by its id
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        code = self.req.get('/Codes/' + id_code, '')
        executions = self.req.get('/Codes/' + id_code + '/executions',
                                  'filter={"limit":3}')
        if isinstance(executions, list):
            code["executions"] = executions
        return code

    def get_image_code(self, id_code):
        '''
        Get the image of a code, by its id
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        return self.req.get('/Codes/' + id_code + '/export/png/url', '')

    def get_last_codes(self):
        '''
        Get the last codes of the user
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        return self.req.get(str('/users/' +
                                self.req.credential.get_user_id() +
                                '/codes/lastest'),
                            '&includeExecutions=true')['codes']

    def run_experiment(self, qasm, device='simulator', shots=1, name=None,
                       seed=None, timeout=60):
        '''
        Execute an experiment
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        data = {}
        qasm = qasm.replace('IBMQASM 2.0;', '')
        qasm = qasm.replace('OPENQASM 2.0;', '')
        data['qasm'] = qasm
        data['codeType'] = 'QASM2'
        if name is None:
            name = str('Experiment #' +
                       datetime.date.today().strftime("%Y%m%d%H%M%S"))
        data['name'] = name

        device_type = self._check_device(device, 'experiment')

        if not device_type:
            respond = {}
            respond["error"] = str("Device " + device +
                                   " not exits in Quantum Experience." +
                                   " Only allow ibmqx2 or simulator")
            return respond

        if (device not in self.__names_device_simulator) and seed:
            respond = {}
            respond["error"] = "Not seed allowed in " + device
            return respond

        if (seed and len(str(seed)) < 11) and str(seed).isdigit():
            execution = self.req.post('/codes/execute', str('&shots=' +
                                                            str(shots) +
                                                            '&seed=' +
                                                            str(seed) +
                                                            '&deviceRunType=' +
                                                            device_type),
                                      json.dumps(data))
        elif seed:
            respond = {}
            respond["error"] = "Not seed allowed. Max 10 digits."
            return respond
        else:
            execution = self.req.post('/codes/execute', str('&shots=' +
                                                            str(shots) +
                                                            '&deviceRunType=' +
                                                            device_type),
                                      json.dumps(data))
        respond = {}
        try:
            status = execution["status"]["id"]
            id_execution = execution["id"]
            result = {}
            respond["status"] = status
            respond["idExecution"] = id_execution
            respond["idCode"] = execution["codeId"]

            if status == "DONE":
                if "result" in execution and "data" in execution["result"]:
                    if "additionalData" in execution["result"]["data"]:
                        result["extraInfo"] = execution["result"]["data"]["additionalData"]
                    if execution["result"]["data"].get('p', None):
                        result["measure"] = execution["result"]["data"]["p"]
                    if execution["result"]["data"].get('valsxyz', None):
                        result["bloch"] = execution["result"]["data"]["valsxyz"]
                    respond["result"] = result

                    return respond
            elif status == "ERROR":
                return respond
            else:
                if timeout:
                    for _ in range(1, timeout):
                        print("Waiting for results...")
                        result = self.get_result_from_execution(id_execution)
                        if result:
                            respond["status"] = 'DONE'
                            respond["result"] = result
                            return respond
                        else:
                            time.sleep(2)
                    return respond
                else:
                    return respond
        except Exception:
            respond["error"] = execution
            return respond

    def run_job(self, qasms, device='simulator', shots=1,
                max_credits=3, seed=None):
        '''
        Execute a job
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        data = {}
        for qasm in qasms:
            qasm['qasm'] = qasm['qasm'].replace('IBMQASM 2.0;', '')
            qasm['qasm'] = qasm['qasm'].replace('OPENQASM 2.0;', '')
        data['qasms'] = qasms
        data['shots'] = shots
        data['maxCredits'] = max_credits
        data['backend'] = {}

        device_type = self._check_device(device, 'job')

        if not device_type:
            respond = {}
            respond["error"] = str("Device " + device +
                                   " not exits in Quantum Experience." +
                                   "Only allow ibmqx2 or simulator")
            return respond

        if (device not in self.__names_device_simulator) and seed:
            respond = {}
            respond["error"] = "Not seed allowed in " + device
            return respond

        if (seed and len(str(seed)) < 11) and str(seed).isdigit():
            data['seed'] = seed
        elif seed:
            respond = {}
            respond["error"] = "Not seed allowed. Max 10 digits."
            return respond

        data['backend']['name'] = device_type

        job = self.req.post('/Jobs', data=json.dumps(data))
        return job

    def get_job(self, id_job):
        '''
        Get the information about a job, by its id
        '''
        if not self._check_credentials() or not id_job:
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        job = self.req.get('/Jobs/' + id_job)
        return job

    def device_status(self, device='ibmqx2'):
        '''
        Get the status of a chip
        '''
        device_type = self._check_device(device, 'status')
        if not device_type:
            respond = {}
            respond["error"] = str("Device " + device +
                                   " not exits in Quantum Experience." +
                                   "Only allow ibmqx2 or simulator")
            return respond
        status = self.req.get('/Status/queue?device=' + device_type,
                              with_token=False)["state"]
        ret = {}
        ret['available'] = False
        if status:
            ret['available'] = True
        return ret

    def device_calibration(self, device='ibmqx2'):
        '''
        Get the calibration of a real chip
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        device_type = self._check_device(device, 'calibration')
        if not device_type:
            respond = {}
            respond["error"] = str("Device " +
                                   device +
                                   " not exits in Quantum Experience" +
                                   " Real Devices. Only allow ibmqx2")
            return respond
        ret = self.req.get('/DeviceStats/statsByDevice/' + device_type,
                           '&raw=true')

        if device_type == 'Real5Qv2':
            device = 'ibmqx2'
        ret = self._beautify_calibration(ret, device)
        return ret

    def device_parameters(self, device='ibmqx2'):
        '''
        Get the parameters of calibration of a real chip
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond
        device_type = self._check_device(device, 'calibration')
        if not device_type:
            respond = {}
            respond["error"] = str("Device " +
                                   device +
                                   " not exits in Quantum Experience" +
                                   " Real Devices. Only allow ibmqx2")
            return respond
        ret = self.req.get('/DeviceStats/statsByDevice/' + device_type,
                           '&raw=true')

        if device_type == 'Real5Qv2':
            device = 'ibmqx2'
        ret = self._beautify_calibration_parameters(ret, device)
        return ret

    def available_devices(self):
        '''
        Get the devices availables to use in the QX Platform
        '''
        if not self._check_credentials():
            respond = {}
            respond["error"] = "Not credentials valid"
            return respond

        devices_real = self.req.get('/Devices/list')
        respond = []
        sim = {}
        sim["name"] = "simulator"
        sim["type"] = "Simulator"
        sim["num_qubits"] = 24
        respond.append(sim)
        for device in devices_real:
            real = {}
            real["type"] = "Real"
            real["name"] = device["serialNumber"]
            if real["name"] == 'Real5Qv2':
                real["name"] = 'ibmqx2'
            topology = self.req.get('/Topologies/'+device["topologyId"])
            if (("topology" in topology) and
                    ("adjacencyMatrix" in topology["topology"])):
                real["topology"] = topology["topology"]["adjacencyMatrix"]
            real["num_qubits"] = topology["qubits"]
            respond.append(real)

        return respond
