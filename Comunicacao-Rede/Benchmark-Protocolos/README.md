# Benchmark de protocolos: ADS, OPC UA e Modbus TCP

Mede, para o **mesmo dado** (um inteiro), o custo de falar com um PLC TwinCAT por três protocolos. Complementa a comparação qualitativa (segurança, buffering, complexidade) das notas do vault com números reais.

> **Status:** o código do benchmark está validado contra servidores simulados (12 testes). **Ainda não há medições em hardware real.** A tabela de resultados abaixo só deve ser preenchida com números produzidos pelo seu controlador.

## O que é medido

| Métrica | Como | O que mostra |
|---|---|---|
| `echo_rtt` | O cliente escreve um número de sequência N em `nIn`; o PLC copia para `nOut` no mesmo ciclo; o tempo vai da escrita até uma leitura devolver N | Custo de uma troca completa, incluindo a espera pelo ciclo do PLC |
| `read_single` | Tempo de uma única leitura | Custo puro do protocolo, sem o ciclo do PLC |

Só o relógio do cliente é usado, então **não é preciso sincronizar relógios**. Por isso `echo_rtt` tem como piso, aproximadamente, o ciclo da task do PLC (veja *Condições* abaixo). Estatísticas: p50, p95, p99, máximo, falhas (eco que não voltou no tempo limite) e operações por segundo, com amostras de aquecimento descartadas.

| Protocolo | Lado PLC | Biblioteca Python | Licença no PLC |
|---|---|---|---|
| ADS | nativo | `pyads` | não precisa |
| OPC UA | TF6100 (servidor) | `asyncua` | TF6100 (trial de 7 dias) |
| Modbus TCP | TF6250 (servidor) | `pymodbus` | TF6250 (trial de 7 dias) |

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
4. ADS não precisa de mais nada além da rota ADS entre o PC e o controlador (`adstool addroute` no Beckhoff RT Linux).
5. **OPC UA:** instale e licencie a TF6100, configure o servidor com o OPC UA Configurator (usuário e senha) e publique `nIn` e `nOut`. Os atributos `{attribute 'OPC.UA.DA' := '1'}` já estão na GVL e o arquivo TMC precisa estar habilitado no projeto PLC (aba *Settings*). Abra o *TwinCAT OPC UA Sample Client*, navegue até as variáveis e copie os **NodeIds** exatos para `node_in` e `node_out` (o índice de namespace, `ns=`, varia).
6. **Modbus TCP:** instale e licencie a TF6250, libere a porta 502 no firewall e ative a configuração. O servidor usa as áreas a partir do endereço 32768. O cliente escreve em `mb_Output_Registers[0]` (função 6) e lê o eco em `mb_Input_Registers[0]` (função 4).

### 2. Lado cliente (Python 3.11 ou superior)
```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (no Linux: source .venv/bin/activate)
pip install -r requirements.txt
```
Edite `config.toml` com o IP, o AmsNetId e os NodeIds. Credenciais do OPC UA vão em variáveis de ambiente, nunca no arquivo:
```bash
set BENCH_OPCUA_USER=usuario
set BENCH_OPCUA_PASSWORD=senha
```

### 3. Dry-run (sem hardware, recomendado antes da primeira medição real)
```bash
python -m bench.sim_servers --cycle-ms 5          # terminal 1
python -m bench.run_all --config config.sim.toml --protocols opcua modbus   # terminal 2
```
No simulador o eco deve ficar em torno do ciclo simulado (5 ms). Isso confirma que o método funciona; os números **não representam** o TwinCAT. ADS não tem simulador.

### 4. Medição real
```bash
python -m bench.run_all --config config.toml --protocols ads opcua modbus
python -m bench.analyze results/<carimbo>
```
Cada execução grava `samples.csv`, `summary.csv` (com alvo, ciclo, rede e SO do cliente) e uma cópia da configuração; `analyze` gera `summary.md` (tabela pronta para colar nas notas) e `rtt.png`. Um protocolo que falhe é pulado, e os outros continuam.

### 5. Testes
```bash
python -m pytest
```

## Condições que mudam o resultado
Registre e mantenha fixos entre execuções: ciclo da task do PLC, carga do controlador, tipo de rede (cabo direto, switch, Wi-Fi), segurança do OPC UA (sem segurança ou assinado e criptografado), e se o cliente roda no mesmo PC do runtime. Rode cada configuração mais de uma vez e compare p95 e p99, não só a mediana.

## Limites conhecidos
- Escopo de dados: um escalar de 16/32 bits. Matrizes e payloads maiores ficam para uma próxima versão.
- ADS usa leitura/escrita por *handle*; notificações (`add_device_notification`) não são medidas.
- OPC UA é medido com leitura/escrita síncrona; assinaturas (*subscriptions*) não entram.
- MQTT e Publisher/Subscriber ficam para uma segunda rodada.
- Os arquivos `plc/*.Tc*` foram escritos à mão e ainda **não foram importados no XAE**.

## Resultados
Nenhuma medição em hardware real ainda. Preencha após a primeira execução:

| Protocolo | Condições (ciclo, rede, segurança) | p50 eco (ms) | p95 eco (ms) | p50 leitura (ms) | Data |
|---|---|---|---|---|---|
| ADS | a medir | | | | |
| OPC UA | a medir | | | | |
| Modbus TCP | a medir | | | | |

Ver também, no vault, a nota *Benchmark de Protocolos* e a comparação qualitativa em *Funcionalidades de Conectividade (TF6100 vs TF6250 vs TF6420)*.
