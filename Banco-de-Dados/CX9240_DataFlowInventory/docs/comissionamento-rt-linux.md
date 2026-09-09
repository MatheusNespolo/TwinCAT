# Comissionamento do CX9240 (Beckhoff RT Linux) — Historiador MQTT → MariaDB

Passo a passo de deploy do nó historiador: pacotes `apt`, banco MariaDB, NTP, firewall `nftables`,
arquivo de configuração, licenças TwinCAT, rota ADS, TwinCAT Database Server, deploy do PLC e
verificação.

Design: [`2026-09-08-cx9240-mqtt-historian-design.md`](2026-09-08-cx9240-mqtt-historian-design.md) ·
Plano: [`2026-09-08-cx9240-mqtt-historian-plan.md`](2026-09-08-cx9240-mqtt-historian-plan.md).

> **Ressalva ARM / RT Linux** (§8, item 14): algumas funcionalidades do TwinCAT podem não estar
> liberadas ou completamente otimizadas para RT Linux em ARM. Fazer um teste de fumaça de cada TF
> (TF6701, TF6020, TF6420) no próprio CX9240 **antes** de fechar o escopo. Os nomes de pacote e de
> membros de biblioteca abaixo são a melhor referência atual e devem ser confirmados no target.

---

## 1. Pré-requisitos

- **CX9240 com Beckhoff RT Linux** já instalado e acessível na rede (ver material *Primeiros passos
  no Beckhoff RT Linux*). Acesso `ssh` com usuário administrativo (`sudo`).
- **PC de engenharia** com **TwinCAT XAE** (Visual Studio ou XAE Shell), build 4026, e um runtime
  TC3 disponível (o próprio CX9240 como target).
- **Conta myBeckhoff** válida (para o Beckhoff Package Server e para ativação de licenças).
- Cópia local deste repositório (`Banco-de-Dados/CX9240_DataFlowInventory/`), incluindo
  `docs/schema.sql` e `historian.conf.example`.

---

## 2. Pacotes (apt)

1. Autenticação do Package Server — criar `/etc/apt/auth.conf.d/bhf.conf` com as credenciais
   myBeckhoff:

   ```
   machine public.beckhoff.com
   login <usuario-myBeckhoff>
   password <senha-myBeckhoff>
   ```

   `sudo chmod 600 /etc/apt/auth.conf.d/bhf.conf`.

2. Atualizar índices:

   ```bash
   sudo apt update
   ```

3. Runtime TwinCAT (XAR / user mode):

   ```bash
   sudo apt install tc31-xar-um
   ```

4. Functions e servidor de banco:

   ```bash
   sudo apt install tf6701-iot-communication tf6420-database-server mariadb-server
   ```

   > ⚠️ **Confirmar os nomes exatos dos pacotes no Beckhoff Package Server para `arm64` /
   > `bookworm`** — podem diferir (sufixos de versão, `tf6020-*` empacotado junto da TF6701 ou
   > separado, etc.). Listar com `apt search tf67` / `apt search tf64` no target.

5. Habilitar e iniciar o MariaDB:

   ```bash
   sudo systemctl enable --now mariadb
   ```

---

## 3. Banco de dados

1. Endurecer a instalação:

   ```bash
   sudo mysql_secure_installation
   ```

   (definir senha de `root`, remover usuários anônimos, remover o banco `test`, recarregar
   privilégios).

2. Criar o usuário da aplicação com privilégio mínimo (só `INSERT`/`SELECT` no `dfi_historian`):

   ```sql
   CREATE USER 'dfi'@'localhost' IDENTIFIED BY '<senha>';
   GRANT INSERT, SELECT ON dfi_historian.* TO 'dfi'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. Aplicar o schema (idempotente). Copiar `docs/schema.sql` para o CX9240 e rodar:

   ```bash
   mysql -u root -p < docs/schema.sql
   ```

   Conferir: `SHOW TABLES IN dfi_historian;` lista `estoque_hist` e `eventos_hist`;
   `DESCRIBE estoque_hist;` mostra `ts_plc` como `datetime(3)` e `origem` como
   `enum('mudanca','periodico')`.

---

## 4. NTP / relógio

1. Instalar um cliente NTP:

   ```bash
   sudo apt install chrony        # ou: usar o systemd-timesyncd já presente
   ```

2. Conferir estado da sincronização:

   ```bash
   timedatectl
   ```

   (`System clock synchronized: yes`, `NTP service: active`).

3. Definir o fuso do CX9240:

   ```bash
   sudo timedatectl set-timezone America/Sao_Paulo
   ```

> **DECISÃO PENDENTE (resolver na bancada):** `F_DfiNowString` hoje retorna **UTC** (há um
> `// TODO` no código). Decidir se o `ts_plc` gravado deve ser **UTC** ou **hora local**:
> - Se **UTC**: manter `F_DfiNowString` como está; documentar que as consultas/dashboards
>   convertem para local.
> - Se **local**: `F_DfiNowString` precisa de conversão de fuso (offset de `America/Sao_Paulo`,
>   com horário de verão se aplicável) antes de formatar a string.
>
> Em qualquer caso, `ts_db` (default do MariaDB) segue o fuso do servidor; a query de auditoria
> `ABS(ts_db - ts_plc)` só é válida depois que essa decisão estiver fechada.

---

## 5. Firewall (nftables)

1. Liberar **entrada** de ADS (TCP 48898) apenas na interface de engenharia. Criar
   `/etc/nftables.conf.d/60-ads.conf` (exemplo do material RT Linux; ajustar o nome da interface):

   ```
   table inet filter {
       chain input {
           iifname "eth0" tcp dport 48898 accept
       }
   }
   ```

2. Recarregar:

   ```bash
   sudo systemctl reload nftables
   ```

3. **MariaDB (3306)** permanece em `127.0.0.1` (loopback) — **sem regra de firewall** e sem
   exposição na rede.

4. **Saída 8883** (broker MQTT TLS, HiveMQ Cloud) só é necessária quando `mqtt_use_tls=1` em
   `historian.conf`. Na bancada com Mosquitto local (`1883`, sem TLS) não há regra de saída
   específica.

---

## 6. Configuração (`/etc/dfi/historian.conf`)

1. Criar o diretório e copiar o modelo:

   ```bash
   sudo mkdir -p /etc/dfi
   sudo cp historian.conf.example /etc/dfi/historian.conf
   sudo chmod 600 /etc/dfi/historian.conf
   ```

2. Editar `/etc/dfi/historian.conf` e preencher os valores reais:
   - `mqtt_host` / `mqtt_port` do broker (Mosquitto de bancada ou HiveMQ Cloud);
   - `mqtt_use_tls`, `mqtt_ca_cert_path`, `mqtt_user`, `mqtt_pass` conforme o broker;
   - `topic_estoque` / `topic_eventos` (default `dataflow/estoque` / `dataflow/eventos`);
   - `db_id=1` — deve casar com o `hDBID` da conexão `DfiDb` no projeto do Database Server;
   - `sample_period_s`, `buffer_size`, `estoque_max` conforme necessidade.

> **Nota:** se o arquivo faltar ou não parsear no arranque, o historiador fica **inerte**
> (`gDiag.bConfigOk = FALSE`) até o PLC ser reiniciado — **não há retry automático**. Validar o
> arquivo antes de ativar o boot project.

---

## 7. Licenças (XAE)

No PC de engenharia, com o projeto aberto e o target = CX9240:

1. `System → License → Manage Licenses`.
2. Marcar os function blocks / runtime necessários:
   - **TF6701** — IoT Communication (MQTT);
   - **TF6020** — JSON Data Interface (`Tc3_JsonXml`);
   - **TF6420** — Database Server;
   - **TC1200** — PLC.
3. `Order Information → 7 Days Trial` (bancada) **ou** ativar a licença definitiva (por device,
   atrelada ao CX9240 — ver §8/item 1 de `necessidades-integracao.md`).
4. `Ctrl+Shift+S` para salvar / ativar; reiniciar o TwinCAT no target se solicitado.

---

## 8. Rota ADS

Criar a rota do PC de engenharia para o CX9240 (`SYSTEM → Routes → Add`, ou via TwinCAT XAE
`Choose Target System → Search`):
- nome amigável;
- `AmsNetId` do CX9240;
- `IP` / hostname;
- tipo de transporte `TCP/IP`, rota estática nos dois lados.

Confirmar que o target aparece como **RUN** (ou **CONFIG**) e que o `AmsNetId` é o mesmo usado no
projeto do Database Server (§9).

---

## 9. TwinCAT Database Server

1. Abrir a solução; menu `TwinCAT → Database Server` (Configurator).
2. `Target NetId` = `AmsNetId` do CX9240.
3. Na conexão **`DfiDb`** (MariaDB, `127.0.0.1:3306`, `hDBID = 1`): preencher o usuário `dfi` e a
   senha criada na §3.
4. Botão **Check** → conexão **verde**. Se falhar: conferir `mariadb` ativo, `GRANT` do usuário
   `dfi`, e se o conector MariaDB nativo da TF6420 está presente no runtime ARM.

> **Confirmar o enum `DBType`** da conexão — o projeto usa `NET_MySQL`. Se a TF6420 no RT Linux
> expuser um valor diferente para MariaDB, ajustar `DfiDb.tcdbsrvdb`.

---

## 10. Deploy do PLC

1. Target = CX9240.
2. **Excluir a pasta `POUs\test` do boot project** na configuração de produção:
   right-click na pasta `test` → *Properties → Build → Exclude from build* (por configuração), ou
   right-click → **Exclude from build**. O boot project de produção **não** contém TcUnit nem as
   suítes de teste.
3. `Activate Configuration`.
4. `Activate Boot Project`.
5. `Login` + `Run`.
6. Conferir `GVL_Dfi.gDiag`: `bConfigOk = TRUE`, `bMqttConnected = TRUE`, `bDbConnected = TRUE`,
   `eWriterState` alternando `IDLE`/`BUILD`/`EXECUTE`/`COMMIT` sem `ERROR` persistente.

---

## 11. Verificação

Rodar o [`roteiro-testes-bancada.md`](roteiro-testes-bancada.md) (8 cenários + pré-requisitos).
Registrar `resultado` / `notas` de cada cenário. O historiador só é considerado comissionado quando
os 8 cenários passam.

---

## Checklist de verificação no XAE (itens deferidos durante o desenvolvimento)

O código foi escrito **sem uma toolchain TwinCAT** disponível. Os itens abaixo **precisam** ser
verificados na primeira abertura em XAE, contra as bibliotecas realmente instaladas no CX9240.
Correções ficam localizadas nos helpers indicados.

- [ ] **Build da solução** — `TwinCAT Project.sln` compila com **0 erros**; as 8+ libs resolvem
  (`Tc2_Standard`, `Tc2_System`, `Tc2_Utilities`, `Tc3_JsonXml`, `Tc3_IotBase`, `Tc3_Database`,
  `Tc3_EventLogger`, `TcUnit`). Instalar os pacotes TF que faltarem.
- [ ] **Task de teste** — `TestTask` (`TestTask.TcTTO` + entrada no `.tsproj` `Id=4` / `AmsPort=351`
  + `<Context Id=1>` em `PLC.xti`) foi escrita à mão por padrão — **verificar / regerar no XAE**
  (normalmente o IDE gerencia isso). `AutoStart` pode faltar.
- [ ] **TcUnit** — instalar o pacote TcUnit; rodar a suíte `PRG_DfiTests`. Esperado verde:
  `FB_DfiRowBuffer_Tests` 5/5, `FB_DfiSampler_Tests` 3/3 (setar o timeout global do TcUnit ≥ 2 s —
  testes baseados em tempo), `FB_DfiCfgParse_Tests` 5/5, `FB_DfiPayloadParser_Tests` 18/18,
  `FB_DfiSqlBuilder_Tests` 5/5, `F_DfiNowString_Tests` (formato), `FB_DfiDbWriter_Tests` 4/4.
- [ ] **`Tc3_JsonXml` (TF6020)** — confirmar os nomes de método usados em `FB_DfiPayloadParser`
  (`ParseDocument` → handle comparado `= 0`, `HasMember`, `FindMember`, `IsString`, `IsInt`,
  `GetString`, `GetInt`) contra a lib instalada; correções ficam nos helpers `HasKey` / `GetStr` /
  `GetInt`.
- [ ] **`Tc2_System` file FBs** — em `FB_DfiConfigLoader`: confirmar `FB_FileGets`
  (`pBuffer` / `cbBuffer` / `bEOF`), `FOPEN_*` (qualificação de namespace) e o caso "última linha
  sem `\n`".
- [ ] **`Tc2_Utilities`** — `F_DfiNowString`: confirmar `GETSYSTEMTIME` / `FILETIME_TO_SYSTEMTIME`
  (nomes de membro `timeLoDW` / `dwLowDateTime` / `systemTime` / `w*`); `FB_DfiSqlBuilder`:
  confirmar `FB_FormatString` (`%d`, `sOut =>`, binding de `arg1..argN`) e `F_String` / `F_INT`.
- [ ] **`Tc3_Database` (TF6420)** — `FB_SQLDatabaseEvt.Connect(hDBID)` / `CreateCmd(ADR(...))` /
  `Disconnect()` / `.bError` / `.ipTcResult`; `FB_SQLCommandEvt.Execute(pSQLCmd, cbSQLCmd)` — o
  writer passa `cbSQLCmd := UINT_TO_UDINT(nCmdLen)` (comprimento real, sem terminador); se a TF6420
  tratar `cbSQLCmd` como tamanho de buffer e não comprimento, testar `nCmdLen + 1` (corta o `;`
  final). Confirmar que `Disconnect()` fire-and-forget na transição de erro não vaza handle de
  sessão.
- [ ] **`Tc3_IotBase` (TF6701)** — `FB_DfiMqttSubscriber`: confirmar `stMQTT.sUserName` (vs
  `sUsername`), `stTLS.sCA`, `Subscribe(sTopic, eQoS)` + `TcIotMqttQos.AtLeastOnceDelivery`, e a
  API de fila `ipMessageQueue` / `nQueuedMessages` / `Dequeue` / `GetTopic` / `GetPayload`;
  correções ficam nos métodos `ApplyBrokerParams` / `EnsureSubscriptions` / `DrainOneMessage`. Se a
  lib só oferecer callback, `DrainOneMessage` vira um ring buffer alimentado pelo callback.
  `GetTopic` usa `SIZEOF(sTopic)` — checar se precisa de `-1` para o terminador.
- [ ] **OOP** — dispatch dos overrides `PROTECTED` (`DoExecute` / `DoConnect`) de
  `FB_DfiDbWriter_Fake` resolve para o fake (late-binding).
- [ ] **Boot project de produção** — `POUs\test` excluída; `PlcTask` cycle 100 ms / prioridade 20;
  `AutoStart` do boot project habilitado.
