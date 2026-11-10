# Benchmark de protocolos: ADS, OPC UA, Modbus TCP e MQTT

Mede, para o **mesmo dado** (um inteiro), o custo de falar com um PLC TwinCAT por quatro protocolos, em seis modos: ADS e OPC UA tanto por leitura em laço (*polling*) quanto por notificação (*push*), Modbus TCP e MQTT. Complementa a comparação qualitativa (segurança, buffering, complexidade) das notas do vault com números reais.

> **Status:** o código do benchmark está validado contra servidores simulados (18 testes). **Ainda não há medições em hardware real.** A tabela de resultados abaixo só deve ser preenchida com números produzidos pelo seu controlador.

## O que é medido

| Métrica | Como | O que mostra |
|---|---|---|
| `echo_rtt` | O cliente escreve (ou publica) um número de sequência N; o PLC o devolve no mesmo ciclo; o tempo vai do envio até N voltar | Custo de uma troca completa, incluindo a espera pelo ciclo do PLC |
| `read_single` | Tempo de uma única leitura (ADS, OPC UA e Modbus) | Custo puro do protocolo, sem o ciclo do PLC |
| `publish_ack` | MQTT: tempo até o broker confirmar (PUBACK) um publish com QoS 1 num tópico sem assinantes | O equivalente de `read_single` para MQTT, que não tem leitura direta; vai só até o broker |

Só o relógio do cliente é usado, então **não é preciso sincronizar relógios**. Por isso `echo_rtt` tem como piso, aproximadamente, o ciclo da task do PLC (veja *Condições* abaixo). Estatísticas: p50, p95, p99, máximo, falhas (eco que não voltou no tempo limite) e operações por segundo, com amostras de aquecimento descartadas.

| Modo | Como a resposta chega | Lado PLC | Biblioteca Python | Licença no PLC |
|---|---|---|---|---|
| `ads` | leitura em laço, por *handle* | nativo | `pyads` | não precisa |
| `ads_notify` | notificação de dispositivo (`add_device_notification`) | nativo | `pyads` | não precisa |
| `opcua` | leitura em laço | TF6100 (servidor) | `asyncua` | TF6100 (trial de 7 dias) |
| `opcua_sub` | assinatura (`subscribe_data_change`) | TF6100 (servidor) | `asyncua` | TF6100 (trial de 7 dias) |
| `modbus` | leitura em laço | TF6250 (servidor) | `pymodbus` | TF6250 (trial de 7 dias) |
| `mqtt` | mensagem publicada pelo PLC (push) | TF6701 (cliente MQTT) | `paho-mqtt` | TF6701 (trial de 7 dias) |

> **Atenção ao comparar o MQTT com os outros.** O caminho é cliente → **broker** → PLC → **broker** → cliente, ou seja, duas passagens pelo broker, e o TF6701 entrega uma mensagem por ciclo do PLC. O número não é comparável diretamente a ADS, OPC UA e Modbus sem essa ressalva. E nos modos *push*, o que o PLC faz por ciclo e o intervalo de amostragem pedido ao servidor entram no resultado.

## Estrutura

```
Benchmark-Protocolos/
├── plc/                 código ST do eco (importar no projeto TwinCAT)
├── bench/               cliente Python: um módulo por protocolo + execução + análise
├── tests/               testes unitários e de integração (contra o simulador)
├── config.toml          configuração do controlador real
├── config.sim.toml      configuração do dry-run (simulador local)
└── results/             saídas (uma pasta por execução)
```

## Passo a passo

### 1. Lado PLC (TwinCAT XAE)
1. Crie um projeto TwinCAT 3 com um projeto PLC e importe os arquivos de `plc/` (botão direito na pasta do projeto PLC, *Add > Existing Item*): `GVL_Bench.TcGVL`, `GVL.TcGVL` e `PRG_Echo.TcPOU`. Se a importação falhar, crie os objetos à mão e cole o texto (as declarações e o ST estão nos próprios arquivos).
2. No `MAIN`, chame `PRG_Echo();`.
3. Defina o ciclo da task do PLC (por exemplo 1 ms) e **anote o valor em `plc_cycle_ms`** no `config.toml`.
4. **ADS** (`ads` e `ads_notify`) não precisa de mais nada além da rota ADS entre o PC e o controlador (`adstool addroute` no Beckhoff RT Linux).
5. **OPC UA** (`opcua` e `opcua_sub`): instale e licencie a TF6100, configure o servidor com o OPC UA Configurator (usuário e senha) e publique `nIn` e `nOut`. Os atributos `{attribute 'OPC.UA.DA' := '1'}` já estão na GVL e o arquivo TMC precisa estar habilitado no projeto PLC (aba *Settings*). Abra o *TwinCAT OPC UA Sample Client*, navegue até as variáveis e copie os **NodeIds** exatos para `node_in` e `node_out` (o índice de namespace, `ns=`, varia).
6. **Modbus TCP:** instale e licencie a TF6250, libere a porta 502 no firewall e ative a configuração. O servidor usa as áreas a partir do endereço 32768. O cliente escreve em `mb_Output_Registers[0]` (função 6) e lê o eco em `mb_Input_Registers[0]` (função 4).
7. **MQTT:** instale e licencie a TF6701 e tenha um broker acessível pelo PC e pelo controlador (por exemplo o Mosquitto do projeto Data Flow Inventory, na porta 1883). Importe também `FB_BenchMqttEcho.TcPOU` e `PRG_EchoMqtt.TcPOU`, adicione a referência **`Tc3_IotBase`** ao projeto PLC, ajuste o endereço do broker em `PRG_EchoMqtt` (o mesmo de `[mqtt] host` no `config.toml`) e chame `PRG_EchoMqtt();` no `MAIN`. O PLC assina `bench/in` e devolve o mesmo payload em `bench/out`. Quem não vai medir MQTT pode ignorar esses dois arquivos: eles ficam separados justamente para não exigir a TF6701.

### 2. Lado cliente (Python 3.11 ou superior)
```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (no Linux: source .venv/bin/activate)
pip install -r requirements.txt
```
Edite `config.toml` com os IPs, o AmsNetId, os NodeIds e o broker. Credenciais vão em variáveis de ambiente, nunca no arquivo:
```bash
set BENCH_OPCUA_USER=usuario
set BENCH_OPCUA_PASSWORD=senha
set BENCH_MQTT_USER=usuario
set BENCH_MQTT_PASSWORD=senha
```

### 3. Dry-run (sem hardware, recomendado antes da primeira medição real)
```bash
python -m bench.sim_servers --cycle-ms 5          # terminal 1
python -m bench.run_all --config config.sim.toml --protocols opcua opcua_sub modbus mqtt   # terminal 2
```
No simulador o eco deve ficar em torno do ciclo simulado (5 ms). Isso confirma que o método funciona; os números **não representam** o TwinCAT. O MQTT do simulador sobe um Mosquitto de teste na porta 18830 (se o `mosquitto` estiver instalado: variável `BENCH_MOSQUITTO`, PATH ou o caminho padrão do Windows), sem usar o serviço Mosquitto do sistema. ADS não tem simulador, então `ads` e `ads_notify` só rodam contra um runtime TwinCAT real (os testes usam uma conexão falsa).

### 4. Medição real
```bash
python -m bench.run_all --config config.toml --protocols ads opcua modbus
python -m bench.run_all --config config.toml --protocols ads_notify opcua_sub mqtt
python -m bench.analyze results/<carimbo>
```
Cada execução grava `samples.csv`, `summary.csv` (com alvo, ciclo, rede e SO do cliente) e uma cópia da configuração; `analyze` gera `summary.md` (tabela pronta para colar nas notas) e `rtt.png`. Um protocolo que falhe ou não esteja configurado é pulado, e os outros continuam.

### 5. Testes
```bash
python -m pytest
```
Os testes de MQTT são pulados se o Mosquitto não estiver instalado. O simulador usado nos testes encerra sozinho (e derruba o Mosquitto de teste) quando o teste termina.

## Condições que mudam o resultado
Registre e mantenha fixos entre execuções: ciclo da task do PLC, carga do controlador, tipo de rede (cabo direto, switch, Wi-Fi), segurança do OPC UA (sem segurança ou assinado e criptografado), QoS e broker do MQTT (local ou em nuvem, com ou sem TLS), e se o cliente roda no mesmo PC do runtime. Nos modos *push*, anote também `notify_cycle_ms` (ADS) e `sub_period_ms` e `sampling_ms` (OPC UA): são valores **pedidos**, e o servidor pode revisá-los para cima. Rode cada configuração mais de uma vez e compare p95 e p99, não só a mediana.

## Limites conhecidos
- Escopo de dados: um escalar de 16/32 bits. Matrizes e payloads maiores ficam para uma próxima versão.
- **Publisher/Subscriber (EAP) não é medido:** ele é PLC a PLC, entre dois runtimes TwinCAT, e não há cliente Python. Medi-lo exigiria carimbos de tempo no PLC com relógios sincronizados (DC/PTP) ou um laço de ida e volta dentro do PLC.
- No MQTT o eco passa duas vezes pelo broker e o TF6701 entrega uma mensagem por ciclo do PLC; o `publish_ack` mede só até o broker.
- Os arquivos `plc/*.Tc*` foram escritos à mão e ainda **não foram importados no XAE**. Em `FB_BenchMqttEcho` a conexão, a fila de entrada, o `Subscribe` e o `Dequeue` seguem o `FB_DfiMqttSubscriber` do projeto `CX9240_DataFlowInventory`, validado em bancada; o `Publish` vem só da documentação da Beckhoff e **não foi testado**.
- ADS por notificação e OPC UA por assinatura medem a entrega por *callback*; não medem o custo de criar a notificação ou a assinatura.

## Resultados
Nenhuma medição em hardware real ainda. Preencha após a primeira execução:

| Modo | Condições (ciclo, rede, segurança) | p50 eco (ms) | p95 eco (ms) | p50 leitura ou ack (ms) | Data |
|---|---|---|---|---|---|
| ads | a medir | | | | |
| ads_notify | a medir | | | n/a | |
| opcua | a medir | | | | |
| opcua_sub | a medir | | | n/a | |
| modbus | a medir | | | | |
| mqtt | a medir | | | | |

Ver também, no vault, a nota *Benchmark de Protocolos* e a comparação qualitativa em *Funcionalidades de Conectividade (TF6100 vs TF6250 vs TF6420)*.
