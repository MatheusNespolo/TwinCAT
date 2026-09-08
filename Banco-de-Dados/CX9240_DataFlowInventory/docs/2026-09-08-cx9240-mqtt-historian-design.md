# CX9240 — Historiador local MQTT → MariaDB para o Data Flow Inventory

- **Data:** 2026-09-08
- **Repositório:** `TwinCAT` (`github.com/MatheusNespolo/TwinCAT`), pasta `Banco-de-Dados/CX9240_DataFlowInventory/`
- **Status:** design aprovado nas 3 seções de brainstorming; pendente auto-revisão e leitura do usuário antes do plano de implementação
- **Autor:** Matheus Nespolo (com Claude)

---

## 1. Objetivo e contexto

Adicionar um **nó historiador local** ao protótipo *Data Flow Inventory* (SENAI São Caetano do Sul):
um PC industrial **Beckhoff CX9240** (ARM Cortex-A53) rodando **Beckhoff RT Linux** e **TwinCAT 3**
(build 4026), que **assina via MQTT** os tópicos de estoque e de eventos publicados hoje pelo gateway
ESP32 e **grava o histórico em um banco MariaDB local** (no próprio CX9240) através da **TF6420 –
TwinCAT Database Server**.

Esta integração é uma **melhoria** do projeto: introduz hardware Beckhoff, persistência histórica
relacional e uma base para dashboards analíticos (Grafana/phpMyAdmin), sem depender do servidor
Node nem de nuvem para reter dados.

### 1.1 Papel na arquitetura

O CX9240 é um **assinante passivo em paralelo**. Nada no caminho atual muda:

```
Arduino Uno ──Serial──> ESP32 ──MQTT──> Broker ──┬──> Node.js Server ──WebSocket──> Dashboard
                                                  │
                                                  └──> CX9240 (TwinCAT 3 / RT Linux)
                                                        FB_IotMqttClient  →  parser JSON
                                                        →  FIFO  →  FB_DfiDbWriter (TF6420)
                                                        →  MariaDB local (127.0.0.1:3306)
```

- **Não** controla I/O físico, **não** roda a FSM da máquina, **não** publica nada (ver §9, regra do
  tópico `dataflow/status`).
- O gateway ESP32 e o servidor Node continuam sendo as únicas fontes/consumidores atuais.

### 1.2 Fora de escopo

- Alterar Arduino, ESP32, servidor Node ou frontend.
- Dashboards/visualização do histórico (Grafana etc.) — apenas citados como necessidade (§8).
- Controle da "roda giratória" de separação (outra melhoria, não relacionada).
- Publicação de qualquer tópico MQTT pelo CX9240.
- Alta disponibilidade / replicação do banco.

### 1.3 Decisões já tomadas (brainstorming)

| Tema | Decisão |
|---|---|
| Papel do CX9240 | Historiador local passivo, em paralelo ao Node |
| O que registrar | `dataflow/estoque` **e** `dataflow/eventos` (entrega/erro) |
| Modelo da tabela de estoque | **Formato largo + amostragem periódica** (INSERT a cada mudança **e** a cada `tSamplePeriod`) |
| Onde roda o banco | **MariaDB no próprio CX9240** (`127.0.0.1:3306`) — Topologia 3 do material da TF6420 |
| Broker | **Configurável**: Mosquitto local `1883` (padrão de bancada) **ou** HiveMQ Cloud `8883`/TLS, numa mesma STRUCT |
| Natureza do entregável | **Deployável** — o design inclui comissionamento (apt, licenças, nftables, NTP, configurador do Database Server) |
| Modo da TF6420 | **SQL Expert Mode** (`FB_SQLDatabaseEvt` / `FB_SQLCommandEvt`), string montada com `FB_FormatString` |
| Abordagem geral | TF6701 (MQTT bruto) + TF6420 SQL Expert Mode + **FIFO de desacoplamento** entre MQTT e banco |

---

## 2. Contrato de dados de entrada (tópicos MQTT existentes)

Fonte: `docs/arquitetura_mqtt.md` do repositório `DataFlowInventory` e o firmware `esp32/gateway_mqtt/gateway_mqtt.ino`.

### 2.1 `dataflow/estoque` — assinar (QoS 1)

- Publicado pelo ESP32 **a cada mudança** de estoque, com flag **retained**.
- Um novo assinante (ou uma reconexão) recebe **imediatamente** a última mensagem retida.

```json
{ "type": "estoque", "pecaA": 4, "pecaB": 5, "pecaC": 5 }
```

O servidor Node também injeta `_timestamp` e `_topic` ao repassar para o WebSocket, mas **isso é
adicionado pelo Node**, não está no payload MQTT — o CX9240 recebe apenas os campos acima.

### 2.2 `dataflow/eventos` — assinar (QoS 1)

- Publicado pelo ESP32 a cada pedido, entrega, erro e inicialização. **Não** retained.

```json
{ "type": "evento", "evento": "entrega", "peca": "A", "estoqueA": 4, "estoqueB": 5, "estoqueC": 5 }
{ "type": "evento", "evento": "erro", "tipo": "timeout", "peca": "B" }
```

Campos considerados: `evento` (string), `peca` (`"A"|"B"|"C"`, pode faltar), `tipo` (string, só em
`erro`). Os campos `estoqueA/B/C` que às vezes acompanham o evento **são ignorados** — a fonte de
verdade do estoque é o tópico `dataflow/estoque`.

### 2.3 Tópicos que o CX9240 NÃO assina

`dataflow/status`, `dataflow/status/server`, `dataflow/sensores`, `dataflow/esteiras`,
`dataflow/comandos/sub`, `dataflow/comandos/pub`. (Ver §9 sobre `dataflow/status`.)

### 2.4 Robustez do contrato

O CX9240 passa a **depender do schema JSON** acima. Uma mudança de payload no Arduino/ESP32
quebraria o log silenciosamente. Mitigações (§8, item 8): contador `nParseErrors` exposto no
diagnóstico + recomendação de campo `schemaVersion` no payload do outro projeto.

---

## 3. Estrutura do projeto

Espelha a convenção do projeto irmão `Banco-de-Dados/DatabaseServer1/` (projeto de conectividade +
projeto PLC lado a lado).

```
Banco-de-Dados/CX9240_DataFlowInventory/
├── README.md                                   # visão geral + índice
├── docs/
│   ├── 2026-09-08-cx9240-mqtt-historian-design.md   # este spec
│   ├── comissionamento-rt-linux.md             # apt, licenças, nftables, NTP, ADS
│   ├── necessidades-integracao.md              # cópia navegável da §8
│   ├── roteiro-testes-bancada.md               # cópia navegável da §7.2
│   └── schema.sql                              # DDL idempotente (§5)
├── TwinCAT Connectivity Project/
│   ├── TwinCAT Connectivity Project.tcconnproj
│   └── TcDatabaseServer/
│       ├── TcDatabaseServer.tcdbsrv
│       └── DfiDb/DfiDb.tcdbsrvdb               # conexão MariaDB 127.0.0.1:3306, hDBID fixo
└── TwinCAT Project/
    ├── TwinCAT Project.sln
    ├── TwinCAT Project.tsproj                  # 1 PlcTask dedicada, baixa prioridade (§10)
    └── PLC/
        ├── PLC.plcproj
        ├── DUTs/
        │   ├── ST_DfiConfig.TcDUT
        │   ├── ST_EstoqueSnapshot.TcDUT
        │   ├── ST_EventoDfi.TcDUT
        │   ├── ST_DfiRow.TcDUT                 # item da FIFO (união estoque|evento + eKind)
        │   ├── E_DfiRowKind.TcDUT
        │   └── E_DfiWriterState.TcDUT
        ├── GVLs/
        │   └── GVL_Dfi.TcGVL                   # instâncias globais + struct de diagnóstico
        └── POUs/
            ├── MAIN.TcPOU
            └── fb/
                ├── FB_DfiMqttSubscriber.TcPOU
                ├── FB_DfiPayloadParser.TcPOU
                ├── FB_DfiRowBuffer.TcPOU
                ├── FB_DfiSampler.TcPOU
                └── FB_DfiDbWriter.TcPOU
```

### 3.1 Bibliotecas referenciadas

| Biblioteca | Origem | Uso |
|---|---|---|
| `Tc3_IotBase` | TF6701 | `FB_IotMqttClient`, `ST_IotMqttTls`, fila de mensagens recebidas |
| `Tc3_JsonXml` | TF6020 | `FB_JsonDomParser` (parse dos payloads) |
| `Tc3_Database` | TF6420 | `FB_SQLDatabaseEvt`, `FB_SQLCommandEvt` |
| `Tc3_EventLogger` | base | `I_TcMessage` (`ipTcResult` dos FBs da TF6420) |
| `Tc2_Utilities` | base | `FB_FormatString` (montagem do SQL), acesso a arquivo p/ config |
| `Tc2_Standard` | base | `TON` |
| `TcUnit` | — | testes unitários (dev only, não vai para o boot project) |

> **Nomes exatos de membros das libs** (ex.: `stTLS` vs `stTls`, `ipMessageQueue`, membros de
> `ST_IotMqttMessage`) serão **fixados na implementação** contra a versão instalada no CX9240 —
> podem variar entre revisões da TF6701. As assinaturas da TF6420 abaixo (§4.4) já foram
> confirmadas na doc.

---

## 4. Arquitetura de function blocks

Cada FB tem uma responsabilidade única e interface explícita. Nenhum FB conhece o interior do outro.

### 4.1 `FB_DfiMqttSubscriber`

Gerencia o `FB_IotMqttClient`: conexão (com/sem TLS conforme `ST_DfiConfig`), subscribe dos dois
tópicos com QoS 1, e retirada de **uma** mensagem por ciclo da fila interna da biblioteca.

```
VAR_INPUT
    stConfig : ST_DfiConfig;
    bEnable  : BOOL;
END_VAR
VAR_OUTPUT
    bConnected      : BOOL;
    bNewMessage     : BOOL;   // TRUE por 1 ciclo quando sTopic/sPayload são válidos
    sTopic          : STRING(255);
    sPayload        : STRING(510);
    nReconnectCount : UDINT;
END_VAR
```

- Reconexão: se cair, re-`Execute(TRUE)` com back-off de 5 s; `nReconnectCount++` a cada
  transição desconectado→conectado perdida.
- TLS: quando `stConfig.bUseTls`, preenche o sub-struct de TLS do cliente com `stConfig.sCaCertPath`
  (CA raiz no filesystem do RT Linux). Loopback do banco **não** usa TLS.
- Autenticação: usa `stConfig.sMqttUser` / `sMqttPass` quando `sMqttUser <> ''`.
- `sClientId` fixo: `dataflow-cx9240-historian` (único no barramento).

### 4.2 `FB_DfiPayloadParser`

Converte **um** payload JSON em `ST_EstoqueSnapshot` **ou** `ST_EventoDfi`, conforme o tópico.
Valida presença de campos, faixas e **sanitiza texto** (único anteparo contra injeção — ver §5.3).

```
VAR_INPUT
    sTopic   : STRING(255);
    sPayload : STRING(510);
    stConfig : ST_DfiConfig;   // limites de faixa configuráveis
END_VAR
VAR_OUTPUT
    bOk         : BOOL;
    eKind       : E_DfiRowKind;         // ESTOQUE_MUDANCA (default) | EVENTO
    stEstoque   : ST_EstoqueSnapshot;
    stEvento    : ST_EventoDfi;
    sParseError : STRING(120);
END_VAR
```

Regras de validação:

| Situação | Resultado |
|---|---|
| JSON inválido / não parseável | `bOk := FALSE`, `sParseError := 'json'` |
| `type` ausente ou diferente de `estoque`/`evento` | `bOk := FALSE`, `sParseError := 'type'` |
| `estoque`: `pecaA/B/C` ausente ou não inteiro | `bOk := FALSE`, `sParseError := 'campo'` |
| `estoque`: valor `< 0` ou `> stConfig.nEstoqueMax` (default 999) | `bOk := FALSE`, `sParseError := 'faixa'` |
| `evento`: `evento` ausente ou vazio | `bOk := FALSE`, `sParseError := 'campo'` |
| `evento`: `peca` presente e ∉ {A,B,C} | `bOk := FALSE`, `sParseError := 'peca'` |
| texto (`evento`, `tipo`) com `'`, `;`, `\`, `"` ou caractere de controle | **rejeitado** (`sParseError := 'sanit'`) — não escapamos, descartamos |
| texto acima do tamanho da coluna | truncado no limite da coluna (§5) |

> Escolha: **rejeitar** texto suspeito em vez de escapar. Os campos de texto vêm de um conjunto
> pequeno e conhecido (`entrega`, `erro`, `timeout`, `inicializacao`, ...). Se aparecer algo fora
> disso, é mais seguro registrar `nParseErrors` do que arriscar um escape imperfeito.

### 4.3 `FB_DfiRowBuffer`

FIFO circular em memória que **desacopla** a taxa do MQTT da latência do banco e funciona como
**store-and-forward** durante quedas curtas do MariaDB.

```
VAR_INPUT
    nCapacity : UDINT := 512;   // vem de stConfig.nBufferSize
END_VAR
METHOD Push : BOOL   // (stRow : ST_DfiRow) — FALSE se descartou o mais antigo
METHOD Peek : BOOL   // (VAR_OUTPUT stRow : ST_DfiRow) — lê a frente sem remover
METHOD Pop  : BOOL   // remove a frente (só após INSERT confirmado)
VAR_OUTPUT
    nCount     : UDINT;
    nHighWater : UDINT;   // pico histórico de nCount
    nDropped   : ULINT;   // total descartado por buffer cheio
END_VAR
```

- Cheio → descarta **o mais antigo**, `nDropped++` (prioriza dado recente; alternativa "descartar o
  novo" foi rejeitada porque enterraria a amostra periódica mais atual).
- `ST_DfiRow` carrega `eKind`, `ts_plc` (carimbado no `Push`), e os campos de estoque **ou** de
  evento.

### 4.4 `FB_DfiDbWriter`

Drena o buffer para o MariaDB via **SQL Expert Mode** da TF6420. Assinaturas confirmadas na doc
Infosys da `Tc3_Database`:

- `FB_SQLDatabaseEvt` — `VAR_INPUT sNetID : T_AmsNetID := ''; tTimeout : TIME := T#5S;`
  `VAR_OUTPUT bBusy, bError : BOOL; ipTcResult : Tc3_EventLogger.I_TcMessage;`
  - `.Connect(hDBID : UDINT := 1) : BOOL` — abre a conexão cujo **ID** foi configurado no projeto
    do Database Server (a conexão `DfiDb`).
  - `.CreateCmd(...)` — inicializa a instância de `FB_SQLCommandEvt` sobre a conexão aberta.
  - `.Disconnect() : BOOL`.
- `FB_SQLCommandEvt` — mesmos `sNetID`/`tTimeout` e `bBusy`/`bError`/`ipTcResult`.
  - `.Execute(pSQLCmd : POINTER TO BYTE; cbSQLCmd : UDINT) : BOOL` — recebe a **string SQL
    completa** por ponteiro + tamanho; retorna TRUE quando termina (inclusive em erro — checar
    `bError` / `ipTcResult`).

```
VAR_INPUT
    stConfig : ST_DfiConfig;
END_VAR
VAR_IN_OUT
    fbBuffer : FB_DfiRowBuffer;
END_VAR
VAR_OUTPUT
    eState          : E_DfiWriterState;
    bDbConnected    : BOOL;
    nRowsWritten    : ULINT;
    nErrors         : ULINT;
    sLastError      : STRING(255);        // texto extraído de ipTcResult
    stUltimoGravado : ST_EstoqueSnapshot; // último estoque com INSERT confirmado
    bUltimoGravadoValido : BOOL;          // FALSE até a 1ª linha de estoque gravada
END_VAR
VAR
    fbDb   : FB_SQLDatabaseEvt;
    fbCmd  : FB_SQLCommandEvt;
    fbFmt  : FB_FormatString;
    sCmd   : STRING(511);
    fbBackoff : TON;
    tBackoff  : TIME := T#2S;   // cresce até T#30S
END_VAR
```

Máquina de estados (`E_DfiWriterState`):

| Estado | Ação | Transição |
|---|---|---|
| `IDLE` | se `fbBuffer.nCount > 0`: se `bDbConnected` → `BUILD`; senão → `CONNECT` | — |
| `CONNECT` | `fbDb.Connect(hDBID := stConfig.nDbId)`; ao ok, `fbDb.CreateCmd(fbCmd)` | ok → `BUILD`; `bError` → `ERROR` |
| `BUILD` | `fbBuffer.Peek(stRow)`; montar `sCmd` com `fbFmt` conforme `stRow.eKind` (§5.2) | `sCmd` pronto → `EXECUTE` |
| `EXECUTE` | `fbCmd.Execute(ADR(sCmd), TO_UDINT(LEN(sCmd)))`; enquanto `bBusy`, aguarda | ok sem erro → `COMMIT`; `bError` → `ERROR`; `bDbConnected` caiu → `DB_LOST` |
| `COMMIT` | `fbBuffer.Pop()`; `nRowsWritten++`; se `eKind ∈ {ESTOQUE_MUDANCA, ESTOQUE_PERIODICO}`, `stUltimoGravado := <estoque da linha>` e `bUltimoGravadoValido := TRUE` (o `MAIN` só lê); `tBackoff := T#2S` | buffer vazio → `IDLE`; senão → `BUILD` |
| `ERROR` | extrair texto de `ipTcResult` p/ `sLastError`; `nErrors++`; **NÃO** faz `Pop` (linha preservada); `fbBackoff(IN := TRUE, PT := tBackoff)`; `tBackoff := MIN(tBackoff * 2, T#30S)` | `fbBackoff.Q` → `IDLE` |
| `DB_LOST` | `bDbConnected := FALSE`; buffer segura tudo (store-and-forward) | → `IDLE` |

Princípios: **peek → execute → pop** (nada some se o INSERT falhar); **um INSERT por ciclo de PLC**
(não bloqueia a task); `Connect`/`CreateCmd` uma única vez enquanto a conexão vive.

### 4.5 `FB_DfiSampler`

`TON` com período `stConfig.tSamplePeriod` (default `T#60S`). A cada disparo, se já houve ao menos um
estoque válido, empurra na FIFO um `ST_DfiRow` `eKind := ESTOQUE_PERIODICO` com o **último estoque
conhecido** (recebido, não necessariamente gravado).

```
VAR_INPUT
    stUltimoEstoque : ST_EstoqueSnapshot;
    bValido         : BOOL;
    tPeriodo        : TIME;
END_VAR
VAR_IN_OUT
    fbBuffer : FB_DfiRowBuffer;
END_VAR
```

### 4.6 Orquestração — `MAIN`

Chamada cíclica na PlcTask dedicada (baixa prioridade, ver §10):

```pascal
// 1. MQTT
fbSub(stConfig := gCfg, bEnable := TRUE);

// 2. Parse + roteamento
IF fbSub.bNewMessage THEN
    fbParser(sTopic := fbSub.sTopic, sPayload := fbSub.sPayload, stConfig := gCfg);
    IF fbParser.bOk THEN
        CASE fbParser.eKind OF
            E_DfiRowKind.ESTOQUE_MUDANCA:
                stUltimoEstoque := fbParser.stEstoque;   // p/ o sampler
                bEstoqueValido  := TRUE;
                // dedupe: compara com o último estoque EFETIVAMENTE GRAVADO (dono: fbWriter)
                IF NOT fbWriter.bUltimoGravadoValido
                   OR EstoqueDiferente(fbParser.stEstoque, fbWriter.stUltimoGravado) THEN
                    fbBuffer.Push(RowDeEstoque(fbParser.stEstoque, ESTOQUE_MUDANCA));
                END_IF
            E_DfiRowKind.EVENTO:
                fbBuffer.Push(RowDeEvento(fbParser.stEvento));
        END_CASE
    ELSE
        gDiag.nParseErrors := gDiag.nParseErrors + 1;
        gDiag.sUltimoParseError := fbParser.sParseError;
    END_IF
END_IF

// 3. Amostra periódica
fbSampler(stUltimoEstoque := stUltimoEstoque, bValido := bEstoqueValido,
          tPeriodo := gCfg.tSamplePeriod, fbBuffer := fbBuffer);

// 4. Dreno para o banco (fbWriter mantém stUltimoGravado internamente)
fbWriter(stConfig := gCfg, fbBuffer := fbBuffer);

// 5. Diagnóstico
AtualizarDiagnostico(gDiag, fbSub, fbBuffer, fbWriter);
```

> **Dedupe:** a comparação é sempre contra o **último estoque efetivamente gravado**
> (`fbWriter.stUltimoGravado`), não contra o último recebido. Assim o *retained* que reaparece a
> cada reconexão MQTT não gera linha `MUDANCA` duplicada, mas uma mudança real sempre gera.
>
> *Borda conhecida:* se um payload idêntico chega enquanto a linha correspondente ainda está na
> FIFO (não commitada), o dedupe não a pega e grava uma linha idêntica extra. Só ocorre sob
> reconexão MQTT muito rápida com banco lento; impacto = uma linha redundante. Não vale um
> segundo nível de comparação contra a fila.

---

## 5. Esquema do banco de dados

### 5.1 DDL — `docs/schema.sql` (idempotente)

```sql
CREATE DATABASE IF NOT EXISTS dfi_historian
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE dfi_historian;

-- Histórico de estoque (formato largo): 1 linha por mudança E por amostra periódica.
CREATE TABLE IF NOT EXISTS estoque_hist (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ts_plc     DATETIME(3)     NOT NULL,       -- carimbo do CX9240 (requer NTP)
  ts_db      TIMESTAMP(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  estoque_a  SMALLINT        NOT NULL,
  estoque_b  SMALLINT        NOT NULL,
  estoque_c  SMALLINT        NOT NULL,
  origem     ENUM('mudanca','periodico') NOT NULL,
  PRIMARY KEY (id),
  KEY ix_estoque_ts (ts_plc)
) ENGINE=InnoDB;

-- Eventos de entrega/erro (dataflow/eventos).
CREATE TABLE IF NOT EXISTS eventos_hist (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ts_plc      DATETIME(3)     NOT NULL,
  ts_db       TIMESTAMP(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  evento      VARCHAR(24)     NOT NULL,      -- 'entrega' | 'erro' | 'inicializacao' | ...
  peca        CHAR(1)         NULL,          -- 'A'|'B'|'C' ou NULL
  detalhe     VARCHAR(64)     NULL,          -- campo "tipo" do payload de erro (ex.: 'timeout')
  payload_raw VARCHAR(255)    NULL,          -- JSON original truncado (auditoria)
  PRIMARY KEY (id),
  KEY ix_eventos_ts (ts_plc)
) ENGINE=InnoDB;
```

Notas:

- `ts_plc` é a **fonte de verdade** da linha (carimbado no `Push` via RTC do CX9240 + fuso).
  `ts_db` é rede de segurança para detectar deriva de relógio (`ABS(ts_db - ts_plc)` grande ⇒ NTP
  fora).
- `payload_raw` só em `eventos_hist` (baixa cadência). Em `estoque_hist` não compensa o custo de
  escrita em flash.
- A estrutura pode ser exportada como DUT pelo **SQL Query Editor → Export Tablestruct to
  TwinCAT3 DUT** para garantir casamento de tipos (fluxo do material da TF6420).
- **Criação das tabelas:** manual no comissionamento (`mysql < schema.sql`). O PLC **não** cria
  schema.

### 5.2 Comandos SQL montados pelo `FB_DfiDbWriter`

Formato com `FB_FormatString` (`%d` para inteiros, `%s` para texto já sanitizado):

```sql
-- ESTOQUE_MUDANCA / ESTOQUE_PERIODICO
INSERT INTO estoque_hist (ts_plc, estoque_a, estoque_b, estoque_c, origem)
VALUES ('%s', %d, %d, %d, '%s');
--        └ts   └A  └B  └C   └'mudanca' | 'periodico'

-- EVENTO
INSERT INTO eventos_hist (ts_plc, evento, peca, detalhe, payload_raw)
VALUES ('%s', '%s', %s, %s, '%s');
--        └ts   └evento └peca* └detalhe* └payload_raw
-- * peca/detalhe: literal 'A' etc. quando presente, ou a palavra NULL (sem aspas) quando ausente
```

`ts_plc` formatado como `YYYY-MM-DD HH:MM:SS.mmm` a partir do `DT`/`ULINT` do RTC.

### 5.3 Sanitização (§4.2) é o único anteparo de injeção

Como `FB_SQLCommandEvt.Execute` **não faz bind de parâmetros**, a string é montada à mão. Portanto:

- Inteiros só entram via `%d` (nunca `%s`).
- `evento` e `detalhe`: allowlist de caracteres `[A-Za-z0-9_ -]`; qualquer `'`, `"`, `;`, `\`,
  backtick ou caractere `< 0x20` ⇒ linha **rejeitada** no parser, não escapada.
- `peca` restrita a `A|B|C` ou `NULL`.
- `payload_raw`: cópia dos primeiros 255 chars do payload original, com o mesmo filtro de aspas.

---

## 6. Configuração e segredos

### 6.1 `ST_DfiConfig`

```
TYPE ST_DfiConfig :
STRUCT
    // MQTT
    sMqttHost      : STRING(120);
    nMqttPort      : UINT  := 1883;
    bUseTls        : BOOL  := FALSE;
    sCaCertPath    : STRING(255) := '/etc/ssl/certs/ca-certificates.crt';
    sMqttUser      : STRING(60);
    sMqttPass      : STRING(60);
    sTopicEstoque  : STRING(120) := 'dataflow/estoque';
    sTopicEventos  : STRING(120) := 'dataflow/eventos';
    // Banco
    nDbId          : UDINT := 1;          // hDBID da conexão DfiDb no projeto Database Server
    // Historiador
    tSamplePeriod  : TIME  := T#60S;
    nBufferSize    : UDINT := 512;
    nEstoqueMax    : INT   := 999;
END_STRUCT
END_TYPE
```

### 6.2 Fonte dos valores — arquivo fora do VCS

- Arquivo `/etc/dfi/historian.conf` no RT Linux, `chmod 600`, **não versionado** (mesmo padrão
  `secrets.h` / `.env` do repositório `DataFlowInventory`; ver incidente já registrado de
  credenciais de Wi-Fi em histórico).
- Lido no arranque do PLC com `FB_FileOpen`/`FB_FileGets` (`Tc2_System`/`Tc2_Utilities`), parse
  `chave=valor` simples, populando `GVL_Dfi.gCfg`.
- Um `historian.conf.example` **versionado** documenta as chaves, sem valores reais.
- Enquanto o arquivo não existe/não parseia: PLC fica em estado `CONFIG_MISSING`, não conecta em
  nada, sinaliza no diagnóstico.

### 6.3 TLS no RT Linux

- CA raiz (ISRG Root X1 para HiveMQ Cloud) presente em `/etc/ssl/certs/`; caminho em
  `sCaCertPath`.
- Banco em `127.0.0.1` ⇒ sem TLS no lado do banco.

---

## 7. Testes

### 7.1 Unitários (TcUnit, rodam no runtime ARM sem broker nem banco)

| Alvo | Casos |
|---|---|
| `FB_DfiPayloadParser` | estoque válido → struct; evento `entrega`; evento `erro`+`tipo:timeout`; JSON truncado / sem `type` / campo faltando → `bOk=FALSE` com `sParseError` certo; estoque `-1` e `1000` → `faixa`; `peca:"D"` → `peca`; `detalhe` com `'`, `;`, `\x01` → `sanit`; `detalhe` longo → truncado |
| `FB_DfiRowBuffer` | ordem FIFO preservada; `Peek` não remove; `Pop` remove; encher além de `nCapacity` → `nDropped++` e descarta o mais antigo; `nHighWater` acompanha o pico |
| `FB_DfiSampler` | dispara em `tPeriodo`; `bValido=FALSE` → não empurra; após 1º estoque → empurra `ESTOQUE_PERIODICO` com o último valor |
| dedupe (`EstoqueDiferente`) | A/B/C iguais → FALSE; qualquer um diferente → TRUE |
| `FB_DfiDbWriter` (com fake de `FB_SQLCommandEvt`) | sucesso → `Pop` + `nRowsWritten++`; erro → **sem** `Pop`, `nErrors++`, back-off 2→4→...→30 s; `DB_LOST` no meio → volta a `IDLE` sem perder linha; `sCmd` montado == string esperada para cada `eKind` (incl. `peca`/`detalhe` NULL) |

O boot project de produção **não** inclui as POUs de teste.

### 7.2 Integração de bancada — `docs/roteiro-testes-bancada.md`

1. `mosquitto_pub -t dataflow/estoque -m '{"type":"estoque","pecaA":4,"pecaB":5,"pecaC":5}'`
   → 1 linha `mudanca` em `estoque_hist`.
2. Sem publicar nada por 3 × `tSamplePeriod` → 3 linhas `periodico` com o mesmo A/B/C.
3. `dataflow/eventos` com `entrega` (peça A) e `erro`/`timeout` (peça B)
   → 2 linhas em `eventos_hist` com `peca`/`detalhe`/`payload_raw` corretos.
4. `systemctl stop mariadb`; publicar 10 mudanças distintas; `systemctl start mariadb`
   → as 10 linhas aparecem **em ordem**; `nDropped = 0`; `nHighWater ≈ 10`.
5. Derrubar o broker 60 s e voltar → **nenhuma** linha `mudanca` duplicada pelo retained;
   série `periodico` sem buraco no intervalo (CX seguiu vivo).
6. Reboot do CX9240 sob carga → banco sem corrupção; no máximo a última transação perdida.
7. Trocar `historian.conf` para HiveMQ Cloud (TLS/8883), reiniciar PLC → reconecta e volta a gravar.
8. Publicar `{"type":"estoque","pecaA":"x"}` e um evento com `detalhe:"'; DROP TABLE eventos_hist;--"`
   → ambas rejeitadas, `nParseErrors += 2`, tabelas intactas.

### 7.3 Carga / soak

Simulador do `DataFlowInventory` rodando algumas horas contra o CX9240. Observar: cycle time da
PlcTask, `nHighWater` do buffer, crescimento das tabelas, I/O de escrita no microSD, uso de CPU do
Cortex-A53.

---

## 8. Relatório — necessidades que a integração pode ocasionar

Também publicado como `docs/necessidades-integracao.md`.

| # | Necessidade | Detalhe / ação |
|---|---|---|
| 1 | **Licenciamento** | TF6701 (IoT/MQTT), TF6020 (JSON Data Interface), TF6420 (Database Server), TC1200 (PLC). Licenças **por device**, atreladas ao CX9240. Confirmar SKUs e **disponibilidade para ARM/RT Linux** com o suporte Beckhoff. Trial de 7 dias só serve para bancada. |
| 2 | **Pacotes no RT Linux** | `sudo apt install tc31-xar-um tf6701-iot-communication tf6420-database-server mariadb-server` (nomes a confirmar no Package Server). Conta myBeckhoff em `/etc/apt/auth.conf.d/bhf.conf`. Validar que os pacotes TF existem para `arm64`/bookworm. |
| 3 | **Driver de banco em ARM** | TF6420 no Linux exige o conector MySQL/MariaDB nativo do runtime. MS SQL nativo não existe em Linux — por isso **MariaDB**. Verificar versão do servidor suportada pela TF6420. |
| 4 | **Desgaste do microSD** | Escrita contínua degrada o cartão. Definir política de retenção (job `DELETE` por data ou partição por range), ajustar `innodb_flush_log_at_trx_commit`, ou mover `datadir` para armazenamento externo. Monitorar espaço livre. |
| 5 | **Sincronismo de relógio** | `chrony`/NTP **obrigatório** no RT Linux — sem ele `ts_plc` deriva. Definir fuso do CX9240. Query de auditoria: `ts_db` vs `ts_plc`. |
| 6 | **Firewall (nftables)** | Regra de entrada para ADS (TCP 48898) na interface de engenharia (`/etc/nftables.conf.d/60-ads.conf`). Saída para o broker cloud (TCP 8883) quando aplicável. 3306 permanece em loopback. |
| 7 | **Segredos** | Credenciais de broker e de banco **fora do VCS** (`/etc/dfi/historian.conf`, `chmod 600`). Mesma regra do `secrets.h`/`.env`. Alinhar com o incidente de Wi-Fi já registrado no outro projeto. |
| 8 | **Acoplamento ao contrato JSON** | O CX9240 passa a depender do schema de `dataflow/estoque` e `dataflow/eventos`. Mudança no Arduino/ESP32 quebra o log **silenciosamente**. Propor `schemaVersion` no payload do outro projeto; alarme quando `nParseErrors` cresce. |
| 9 | **Papel no barramento MQTT** | O novo assinante é transparente. Se um dia o CX9240 for **publicar** algo, respeitar a regra "`dataflow/status` é exclusivo do ESP32" (CHANGELOG do `DataFlowInventory`) — usar um tópico próprio, ex.: `dataflow/status/historian`. |
| 10 | **Impacto de tempo real** | Os FBs de MQTT e de banco rodam numa **PlcTask separada e de baixa prioridade**, nunca junto de lógica crítica. Medir cycle time no Cortex-A53 sob carga. |
| 11 | **Energia** | UPS de 1 s do CX9240 (variáveis persistentes) + configuração do MariaDB para minimizar perda/corrupção em queda abrupta. Risco residual: última transação. |
| 12 | **Operação do dado** | Como consultar o histórico (Grafana / phpMyAdmin — o README do `DataFlowInventory` já cita Grafana/InfluxDB como assunto futuro). Rotina de **backup** do `dfi_historian`. Dono do schema e processo de migração. |
| 13 | **Comissionamento / competências** | PC de engenharia com TwinCAT XAE; criação de **rota ADS** para o CX9240; `Target NetId` correto no projeto do Database Server; `Add New Database` + botões `Check`/`Create`; ativação de licença trial/definitiva. |
| 14 | **Ressalva geral ARM/RT Linux** | "Algumas funcionalidades do TwinCAT podem não estar liberadas ou completamente otimizadas para esse sistema operacional" (material *Primeiros passos no Beckhoff RT Linux*). Fazer **teste de fumaça de cada TF** no target **antes** de fechar o escopo de implementação. |

---

## 9. Regras herdadas do projeto `DataFlowInventory`

- `dataflow/status` é **exclusivo do gateway ESP32** (retained + LWT). O CX9240 **não publica**
  nada — nem nesse tópico nem em outro. Se isso mudar no futuro, tópico próprio
  (`dataflow/status/historian`).
- Nomes de tópicos são configuráveis; default mantém `dataflow/estoque` e `dataflow/eventos`.
- Segredos nunca no código-fonte (ver §6.2).
- `clientId` MQTT único: `dataflow-cx9240-historian`.

---

## 10. Notas de implementação

- **Task PLC:** uma `PlcTask` dedicada, prioridade **baixa** (maior número), cycle time ~50–100 ms
  — o historiador não tem requisito de tempo real. Isola o custo de MQTT/JSON/SQL da eventual
  lógica de controle futura no mesmo CX.
- **Boot project:** habilitar autostart do PLC; validar `Activate Boot Project`.
- **`cbSQLCmd`:** usar `TO_UDINT(LEN(sCmd))` (comprimento real), não `SIZEOF(sCmd)` (buffer
  inteiro). Buffer `sCmd : STRING(511)` cobre com folga os INSERTs previstos.
- **Extração de erro:** `ipTcResult` (`I_TcMessage`) → texto legível via `Tc3_EventLogger` para
  `sLastError` / `GVL_Dfi`.
- **Reconexão do banco:** `Connect`/`CreateCmd` só uma vez por vida da conexão; em `bError` de
  conexão, `Disconnect` antes de novo `Connect`.
- **`GVL_Dfi.gDiag`:** struct única com `bMqttConnected`, `bDbConnected`, `nReconnectCount`,
  `nCount`, `nHighWater`, `nDropped`, `nRowsWritten`, `nErrors`, `nParseErrors`,
  `sUltimoParseError`, `sLastError`, `eWriterState` — ponto único de observabilidade (ADS/HMI).

---

## 11. Trabalho futuro (fora deste spec)

- Dashboard do histórico (Grafana sobre o MariaDB).
- Job de retenção/particionamento das tabelas.
- Campo `schemaVersion` no payload do `DataFlowInventory` + verificação no parser.
- Eventual segunda tabela de disponibilidade do gateway (`dataflow/status` via LWT), se se quiser
  auditar lacunas no histórico.
- Documentação da melhoria no repositório `DataFlowInventory` (por outro agente).
