# CX9240 MQTT Historian — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TwinCAT 3 Structured Text application for a Beckhoff CX9240 (Beckhoff RT Linux) that subscribes to the Data Flow Inventory MQTT topics and persists stock/event history into a local MariaDB via TF6420.

**Architecture:** A single low-priority PLC task runs a pipeline of focused function blocks: `FB_DfiMqttSubscriber` (TF6701 MQTT client) → `FB_DfiPayloadParser` (Tc3_JsonXml) → `FB_DfiRowBuffer` (in-memory FIFO, store-and-forward) → `FB_DfiDbWriter` (TF6420 SQL Expert Mode, string built with `FB_FormatString`). `FB_DfiSampler` injects a periodic stock snapshot. `MAIN` orchestrates and publishes diagnostics into `GVL_Dfi`. Config and secrets are read at startup from `/etc/dfi/historian.conf` (outside VCS).

**Tech Stack:** TwinCAT 3 (build 4026), Structured Text; libraries `Tc3_IotBase` (TF6701), `Tc3_JsonXml` (TF6020), `Tc3_Database` (TF6420), `Tc3_EventLogger`, `Tc2_Utilities`, `Tc2_Standard`, `Tc2_System`; TcUnit for unit tests; MariaDB on Beckhoff RT Linux (ARM64).

**Spec:** `Banco-de-Dados/CX9240_DataFlowInventory/docs/2026-09-08-cx9240-mqtt-historian-design.md` (read it alongside this plan).

## Global Constraints

- **Repository:** `TwinCAT` (`github.com/MatheusNespolo/TwinCAT`). All work lives under `Banco-de-Dados/CX9240_DataFlowInventory/`. Branch: `feat/cx9240-mqtt-historian` (already created; the spec is already committed there).
- **File-format authority:** `.TcPOU` / `.TcDUT` / `.TcGVL` / `.plcproj` / `.tsproj` / `.sln` / `.tcconnproj` / `.tcdbsrvdb` are XML. Copy structure verbatim from the sibling project `Banco-de-Dados/DatabaseServer1/` and adapt. **Every `<POU>` / `<DUT>` / `<GVL>` element needs a fresh unique GUID** in its `Id="{...}"` attribute (generate a new UUID v4 per object; never reuse one from `DatabaseServer1`).
- **Build/test verification requires TwinCAT XAE + a TC3 runtime** (local Windows TC3 XAR in *Config → Run*, or the CX9240 target). The coding agent produces source artifacts; a human runs the build and TcUnit at the steps marked **⛳ CHECKPOINT** and reports pass/fail. TDD ordering is still mandatory: the test POU is authored before the implementation POU in every FB task.
- **TF6420 call idioms — copied from the working `DatabaseServer1/EscreverDB.TcPOU`, do not "improve":**
  - `SQLDatabaseEvt.Connect(hDBID := <id>)` returns `BOOL` (TRUE when finished); check `.bError`, capture `.ipTcResult` on error.
  - `SQLDatabaseEvt.CreateCmd(ADR(SQLCommandEvt))` — pass the **address** of the command FB.
  - `SQLCommandEvt.Execute(pSQLCmd := ADR(sCmd), cbSQLCmd := SIZEOF(sCmd))` — `DatabaseServer1` uses `SIZEOF`; keep `SIZEOF` (the DB server reads to the null terminator). This overrides the spec §10 note that suggested `LEN`.
  - `SQLDatabaseEvt.Disconnect()` returns `BOOL`.
  - Error text: `ipTcResult.RequestEventText(1033, s, SIZEOF(s))`, `ipTcResult.RequestEventClassName(1033, s, SIZEOF(s))`, `ipTcResult.nEventId`, `ipTcResult.eSeverity` (`TcEventSeverity.Error` / `.Critical`).
- **`FB_FormatString` idiom:** `fb(sFormat := s, arg1 := F_String(a), arg2 := F_INT(n), ..., sOut => sResult);` — string args wrapped with `F_String()`, integers with `F_INT()` / `F_DINT()`.
- **SQL injection anteparo:** integers only ever formatted with `%d`/`F_INT`; text fields (`evento`, `detalhe`, `payload_raw`) must pass the allowlist `[A-Za-z0-9_ -]` in the parser — any `'`, `"`, `;`, `\`, backtick or byte `< 16#20` ⇒ **reject the row** (never escape). `peca` ∈ {`A`,`B`,`C`} or SQL literal `NULL`.
- **`clientId` MQTT:** `dataflow-cx9240-historian` (fixed, unique on the bus).
- **The CX9240 never publishes any MQTT topic.** Subscriber only.
- **Secrets never in VCS:** real values live in `/etc/dfi/historian.conf` (`chmod 600`). Only `historian.conf.example` (no real values) is committed.
- **Commit after every task** with a message prefixed `feat:` / `test:` / `docs:` / `chore:` and the Co-Authored-By trailer:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`
- **Plan/spec live at** `Banco-de-Dados/CX9240_DataFlowInventory/docs/` (project-local, matching where the spec was placed — overrides the skill default of `docs/superpowers/plans/`).

---

## File Structure

**Created by this plan (all under `Banco-de-Dados/CX9240_DataFlowInventory/`):**

| Path | Responsibility |
|---|---|
| `README.md` | Project overview + index + how to open/deploy |
| `.gitignore` (append at repo root) | ignore `historian.conf`, TwinCAT build artifacts already covered |
| `historian.conf.example` | documented config keys, no real values |
| `docs/schema.sql` | idempotent DDL for `dfi_historian` (2 tables) |
| `docs/comissionamento-rt-linux.md` | apt, licenses, MariaDB, nftables, NTP, ADS route, Database Server config |
| `docs/necessidades-integracao.md` | navigable copy of spec §8 (14 items) |
| `docs/roteiro-testes-bancada.md` | navigable copy of spec §7.2 (8 scenarios) |
| `TwinCAT Project/TwinCAT Project.sln` | VS/XAE solution |
| `TwinCAT Project/TwinCAT Project.tsproj` | TwinCAT system project; 1 dedicated low-priority `PlcTask` |
| `TwinCAT Project/PLC/PLC.plcproj` | PLC project, library references |
| `TwinCAT Project/PLC/POUs/MAIN.TcPOU` | orchestration + diagnostics wiring |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiMqttSubscriber.TcPOU` | MQTT connect/subscribe/dequeue (TF6701) |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiPayloadParser.TcPOU` | JSON payload → struct + validate + sanitize |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiRowBuffer.TcPOU` | circular FIFO of `ST_DfiRow` |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiSampler.TcPOU` | periodic snapshot injector (TON) |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiSqlBuilder.TcPOU` | `ST_DfiRow` → INSERT string (`FB_FormatString`) |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiDbWriter.TcPOU` | TF6420 state machine, drains the FIFO |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiCfgParse.TcPOU` | `chave=valor` text → `ST_DfiConfig` (pure) |
| `TwinCAT Project/PLC/POUs/fb/FB_DfiConfigLoader.TcPOU` | read `/etc/dfi/historian.conf`, call `FB_DfiCfgParse` |
| `TwinCAT Project/PLC/DUTs/*.TcDUT` | `ST_DfiConfig`, `ST_EstoqueSnapshot`, `ST_EventoDfi`, `ST_DfiRow`, `ST_DfiDiag`, `E_DfiRowKind`, `E_DfiWriterState` |
| `TwinCAT Project/PLC/GVLs/GVL_Dfi.TcGVL` | global FB instances + `gCfg` + `gDiag` |
| `TwinCAT Project/PLC/POUs/test/*.TcPOU` | TcUnit suites (excluded from boot project) |
| `TwinCAT Project/PLC/POUs/test/PRG_DfiTests.TcPOU` | TcUnit runner program |
| `TwinCAT Connectivity Project/TwinCAT Connectivity Project.tcconnproj` | connectivity project shell |
| `TwinCAT Connectivity Project/TcDatabaseServer/TcDatabaseServer.tcdbsrv` | Database Server project |
| `TwinCAT Connectivity Project/TcDatabaseServer/DfiDb/DfiDb.tcdbsrvdb` | MariaDB connection, `127.0.0.1:3306`, hDBID = 1 |

**Read for reference (do not modify):** `Banco-de-Dados/DatabaseServer1/**`, `../DataFlowInventory/docs/arquitetura_mqtt.md`, `../DataFlowInventory/esp32/gateway_mqtt/gateway_mqtt.ino`.

---

## Task 1: Database schema

**Files:**
- Create: `Banco-de-Dados/CX9240_DataFlowInventory/docs/schema.sql`

**Interfaces:**
- Produces: tables `dfi_historian.estoque_hist(id, ts_plc DATETIME(3), ts_db TIMESTAMP(3), estoque_a SMALLINT, estoque_b SMALLINT, estoque_c SMALLINT, origem ENUM('mudanca','periodico'))` and `dfi_historian.eventos_hist(id, ts_plc DATETIME(3), ts_db TIMESTAMP(3), evento VARCHAR(24), peca CHAR(1) NULL, detalhe VARCHAR(64) NULL, payload_raw VARCHAR(255) NULL)`. `FB_DfiSqlBuilder` (Task 10) targets exactly these column names/order.

- [ ] **Step 1: Write `schema.sql`** (verbatim from spec §5.1)

```sql
-- dfi_historian schema — CX9240 MQTT historian
-- Idempotent: safe to run repeatedly. Run on the CX9240:  mysql -u root -p < schema.sql
CREATE DATABASE IF NOT EXISTS dfi_historian
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE dfi_historian;

CREATE TABLE IF NOT EXISTS estoque_hist (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ts_plc     DATETIME(3)     NOT NULL,
  ts_db      TIMESTAMP(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  estoque_a  SMALLINT        NOT NULL,
  estoque_b  SMALLINT        NOT NULL,
  estoque_c  SMALLINT        NOT NULL,
  origem     ENUM('mudanca','periodico') NOT NULL,
  PRIMARY KEY (id),
  KEY ix_estoque_ts (ts_plc)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS eventos_hist (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ts_plc      DATETIME(3)     NOT NULL,
  ts_db       TIMESTAMP(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  evento      VARCHAR(24)     NOT NULL,
  peca        CHAR(1)         NULL,
  detalhe     VARCHAR(64)     NULL,
  payload_raw VARCHAR(255)    NULL,
  PRIMARY KEY (id),
  KEY ix_eventos_ts (ts_plc)
) ENGINE=InnoDB;
```

- [ ] **Step 2: Verify idempotency (human, on any MariaDB ≥ 10.5)**

Run: `mysql -u root -p < docs/schema.sql` twice.
Expected: no error on the second run; `SHOW TABLES IN dfi_historian;` lists `estoque_hist`, `eventos_hist`; `DESCRIBE estoque_hist;` shows `ts_plc` as `datetime(3)` and `origem` as `enum('mudanca','periodico')`.

- [ ] **Step 3: Commit**

```bash
git add "Banco-de-Dados/CX9240_DataFlowInventory/docs/schema.sql"
git commit -m "feat: add dfi_historian DB schema" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Repo scaffold (README, config example, gitignore)

**Files:**
- Create: `Banco-de-Dados/CX9240_DataFlowInventory/README.md`
- Create: `Banco-de-Dados/CX9240_DataFlowInventory/historian.conf.example`
- Modify: `.gitignore` (repo root) — append one line

**Interfaces:**
- Produces: the config-key contract that `FB_DfiCfgParse` (Task 8) must parse — keys `mqtt_host`, `mqtt_port`, `mqtt_use_tls`, `mqtt_ca_cert_path`, `mqtt_user`, `mqtt_pass`, `topic_estoque`, `topic_eventos`, `db_id`, `sample_period_s`, `buffer_size`, `estoque_max`.

- [ ] **Step 1: Write `historian.conf.example`**

```ini
# /etc/dfi/historian.conf  —  copy to the CX9240, chmod 600, fill real values.
# Lines starting with # and blank lines are ignored. Format: key=value (no quotes, no spaces around =).

# --- MQTT broker ---
mqtt_host=192.168.0.50
mqtt_port=1883
mqtt_use_tls=0                     # 0 = plain (Mosquitto local) | 1 = TLS (HiveMQ Cloud 8883)
mqtt_ca_cert_path=/etc/ssl/certs/ca-certificates.crt
mqtt_user=
mqtt_pass=
topic_estoque=dataflow/estoque
topic_eventos=dataflow/eventos

# --- Database (local MariaDB) ---
db_id=1                            # hDBID of the DfiDb connection in the TwinCAT Database Server project

# --- Historian ---
sample_period_s=60                # periodic stock snapshot interval, seconds
buffer_size=512                   # in-memory FIFO capacity (rows)
estoque_max=999                   # reject stock values outside 0..estoque_max
```

- [ ] **Step 2: Write `README.md`**

```markdown
# CX9240_DataFlowInventory — Historiador local MQTT → MariaDB

Nó historiador para o protótipo [Data Flow Inventory](https://github.com/MatheusNespolo/DataFlowInventory).
Um Beckhoff **CX9240** com **RT Linux** assina os tópicos MQTT `dataflow/estoque` e
`dataflow/eventos` (via TF6701) e grava o histórico num **MariaDB local** (via TF6420,
SQL Expert Mode).

Arduino, ESP32, servidor Node e dashboard do outro projeto **não mudam** — este nó é um
assinante passivo em paralelo.

## Conteúdo

| Pasta / arquivo | O que é |
|---|---|
| `docs/2026-09-08-cx9240-mqtt-historian-design.md` | Spec de design |
| `docs/2026-09-08-cx9240-mqtt-historian-plan.md` | Plano de implementação |
| `docs/schema.sql` | DDL do banco `dfi_historian` |
| `docs/comissionamento-rt-linux.md` | Passo a passo de deploy (apt, licenças, nftables, NTP, ADS) |
| `docs/necessidades-integracao.md` | Necessidades que a integração ocasiona |
| `docs/roteiro-testes-bancada.md` | Roteiro de testes de integração |
| `historian.conf.example` | Modelo do arquivo de configuração (copiar para `/etc/dfi/historian.conf`) |
| `TwinCAT Project/` | Projeto PLC (POUs, DUTs, GVLs, testes TcUnit) |
| `TwinCAT Connectivity Project/` | Projeto do TwinCAT Database Server (conexão `DfiDb`) |

## Como abrir

1. TwinCAT XAE Shell ou Visual Studio com TwinCAT 3, e um runtime TC3 (local XAR ou o CX9240).
2. Abrir `TwinCAT Project/TwinCAT Project.sln`.
3. Licenças de trial/definitivas: TF6701, TF6020, TF6420, TC1200.
4. Deploy: seguir `docs/comissionamento-rt-linux.md`.

## Configuração e segredos

Credenciais **não** ficam no código. Copiar `historian.conf.example` para
`/etc/dfi/historian.conf` no CX9240, `chmod 600`, preencher. O PLC lê esse arquivo no arranque.
```

- [ ] **Step 3: Append to repo-root `.gitignore`**

Add these lines at the end of `C:/Users/matheusn/Documents/GitHub/TwinCAT/.gitignore`:

```gitignore

# CX9240 historian — local secrets, never commit
historian.conf
**/historian.conf
```

- [ ] **Step 4: Commit**

```bash
git add "Banco-de-Dados/CX9240_DataFlowInventory/README.md" "Banco-de-Dados/CX9240_DataFlowInventory/historian.conf.example" .gitignore
git commit -m "chore: scaffold CX9240 historian project (README, config example, gitignore)" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: TwinCAT solution skeleton

**Files:**
- Create: `TwinCAT Project/TwinCAT Project.sln`
- Create: `TwinCAT Project/TwinCAT Project.tsproj`
- Create: `TwinCAT Project/PLC/PLC.plcproj`
- Create: `TwinCAT Project/PLC/POUs/MAIN.TcPOU`
- Reference: `Banco-de-Dados/DatabaseServer1/TwinCAT Project1/**` (copy + adapt every XML file)

**Interfaces:**
- Produces: a buildable (empty-logic) PLC project named `PLC`, with library references `Tc2_Standard`, `Tc2_System`, `Tc2_Utilities`, `Tc3_JsonXml`, `Tc3_IotBase`, `Tc3_Database`, `Tc3_EventLogger`, `Tc3_DynamicVars` (if needed by TcUnit later), and one `PlcTask` at low priority. `MAIN` is `PROGRAM MAIN` with empty body.

- [ ] **Step 1: Copy the `DatabaseServer1` project tree as the template**

Copy `Banco-de-Dados/DatabaseServer1/TwinCAT Project1/` → `Banco-de-Dados/CX9240_DataFlowInventory/TwinCAT Project/`, then:
- Rename `TwinCAT Project1.sln` → `TwinCAT Project.sln`, `TwinCAT Project1.tsproj` → `TwinCAT Project.tsproj`.
- In every copied XML file, replace the project name string `TwinCAT Project1` with `TwinCAT Project`.
- Delete the copied `PLC/POUs/EscreverDB.TcPOU`, `PLC/POUs/LerDB.TcPOU`, `PLC/DUTs/ST_VALORES.TcDUT` (we write our own).
- Regenerate **every** `Id="{...}"` GUID in the copied `.tsproj`/`.plcproj`/`_Config` files to fresh UUIDs so the two projects never collide if both are ever loaded in one solution.

- [ ] **Step 2: Set the PLC project name and task**

In `PLC/PLC.plcproj`: set `<Name>PLC</Name>` and the output/boot settings. In `TwinCAT Project.tsproj` under the PLC/Tasks node, ensure exactly one `PlcTask`:
- `Priority` = a high number (low priority), e.g. `20` (below any control task).
- `CycleTime` = `100000` (100 ms, in 100 ns units → `1000000`? use the same unit the copied file uses — match `DatabaseServer1`'s `CycleTime` attribute format and just change the value to 100 ms equivalent).
- `AutoStart` = `true`.

- [ ] **Step 3: Add library references**

In `PLC/PLC.plcproj`, in the `<ItemGroup>` that holds `<PlaceholderReference>` / `<LibraryReference>` entries (copy the shape from `DatabaseServer1/TwinCAT Project1/PLC/PLC.plcproj`), ensure entries exist for:
`Tc2_Standard`, `Tc2_System`, `Tc2_Utilities`, `Tc3_JsonXml`, `Tc3_IotBase`, `Tc3_Database`, `Tc3_EventLogger`.
Use `* (Beckhoff Automation GmbH)` as the version placeholder like the sibling project does.

- [ ] **Step 4: Write `MAIN.TcPOU`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="MAIN" Id="{GENERATE-NEW-GUID-1}" SpecialFunc="None">
    <Declaration><![CDATA[PROGRAM MAIN
VAR
END_VAR
]]></Declaration>
    <Implementation>
      <ST><![CDATA[// Orquestração preenchida na Task 14.
]]></ST>
    </Implementation>
  </POU>
</TcPlcObject>
```

- [ ] **Step 5: ⛳ CHECKPOINT (human) — build the empty solution**

Open `TwinCAT Project.sln` in XAE → *Build → Build Solution*.
Expected: **0 errors**. All 7 libraries resolve (install missing TF packages first if the reference is red). The PLC task appears under the PLC project.

- [ ] **Step 6: Commit**

```bash
git add "Banco-de-Dados/CX9240_DataFlowInventory/TwinCAT Project"
git commit -m "chore: TwinCAT solution skeleton for CX9240 historian" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: DUTs and GVL

**Files:**
- Create: `TwinCAT Project/PLC/DUTs/E_DfiRowKind.TcDUT`
- Create: `TwinCAT Project/PLC/DUTs/E_DfiWriterState.TcDUT`
- Create: `TwinCAT Project/PLC/DUTs/ST_EstoqueSnapshot.TcDUT`
- Create: `TwinCAT Project/PLC/DUTs/ST_EventoDfi.TcDUT`
- Create: `TwinCAT Project/PLC/DUTs/ST_DfiRow.TcDUT`
- Create: `TwinCAT Project/PLC/DUTs/ST_DfiConfig.TcDUT`
- Create: `TwinCAT Project/PLC/DUTs/ST_DfiDiag.TcDUT`
- Create: `TwinCAT Project/PLC/GVLs/GVL_Dfi.TcGVL`

**Interfaces:**
- Produces (every later task consumes these exact names/types):
  - `E_DfiRowKind : (ESTOQUE_MUDANCA := 0, ESTOQUE_PERIODICO := 1, EVENTO := 2)`
  - `E_DfiWriterState : (IDLE := 0, CONNECT := 10, BUILD := 20, EXECUTE := 30, COMMIT := 40, ERROR := 90, DB_LOST := 99)`
  - `ST_EstoqueSnapshot : STRUCT nA : INT; nB : INT; nC : INT; END_STRUCT`
  - `ST_EventoDfi : STRUCT sEvento : STRING(23); sPeca : STRING(1); sDetalhe : STRING(63); sPayloadRaw : STRING(254); END_STRUCT`
  - `ST_DfiRow : STRUCT eKind : E_DfiRowKind; sTsPlc : STRING(23); stEstoque : ST_EstoqueSnapshot; stEvento : ST_EventoDfi; END_STRUCT`
  - `ST_DfiConfig` — fields per Step 5 below.
  - `ST_DfiDiag` — fields per Step 7 below.
  - `GVL_Dfi` with `gCfg : ST_DfiConfig;` and `gDiag : ST_DfiDiag;`

- [ ] **Step 1: `E_DfiRowKind.TcDUT`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <DUT Name="E_DfiRowKind" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[TYPE E_DfiRowKind :
(
	ESTOQUE_MUDANCA := 0,
	ESTOQUE_PERIODICO := 1,
	EVENTO := 2
) DINT;
END_TYPE
]]></Declaration>
  </DUT>
</TcPlcObject>
```

- [ ] **Step 2: `E_DfiWriterState.TcDUT`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <DUT Name="E_DfiWriterState" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[TYPE E_DfiWriterState :
(
	IDLE := 0,
	CONNECT := 10,
	BUILD := 20,
	EXECUTE := 30,
	COMMIT := 40,
	ERROR := 90,
	DB_LOST := 99
) DINT;
END_TYPE
]]></Declaration>
  </DUT>
</TcPlcObject>
```

- [ ] **Step 3: `ST_EstoqueSnapshot.TcDUT` and `ST_EventoDfi.TcDUT`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <DUT Name="ST_EstoqueSnapshot" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[TYPE ST_EstoqueSnapshot :
STRUCT
	nA : INT;
	nB : INT;
	nC : INT;
END_STRUCT
END_TYPE
]]></Declaration>
  </DUT>
</TcPlcObject>
```

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <DUT Name="ST_EventoDfi" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[TYPE ST_EventoDfi :
STRUCT
	sEvento     : STRING(23);   // coluna eventos_hist.evento VARCHAR(24)
	sPeca       : STRING(1);    // 'A'|'B'|'C' ou '' (=> NULL)
	sDetalhe    : STRING(63);   // coluna detalhe VARCHAR(64)
	sPayloadRaw : STRING(254);  // coluna payload_raw VARCHAR(255)
END_STRUCT
END_TYPE
]]></Declaration>
  </DUT>
</TcPlcObject>
```

- [ ] **Step 4: `ST_DfiRow.TcDUT`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <DUT Name="ST_DfiRow" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[TYPE ST_DfiRow :
STRUCT
	eKind     : E_DfiRowKind;
	sTsPlc    : STRING(23);   // 'YYYY-MM-DD HH:MM:SS.mmm', carimbado no Push
	stEstoque : ST_EstoqueSnapshot;
	stEvento  : ST_EventoDfi;
END_STRUCT
END_TYPE
]]></Declaration>
  </DUT>
</TcPlcObject>
```

- [ ] **Step 5: `ST_DfiConfig.TcDUT`** (spec §6.1, key names aligned with `historian.conf`)

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <DUT Name="ST_DfiConfig" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[TYPE ST_DfiConfig :
STRUCT
	sMqttHost     : STRING(120);
	nMqttPort     : UINT  := 1883;
	bUseTls       : BOOL  := FALSE;
	sCaCertPath   : STRING(255) := '/etc/ssl/certs/ca-certificates.crt';
	sMqttUser     : STRING(60);
	sMqttPass     : STRING(60);
	sTopicEstoque : STRING(120) := 'dataflow/estoque';
	sTopicEventos : STRING(120) := 'dataflow/eventos';
	nDbId         : UDINT := 1;
	tSamplePeriod : TIME  := T#60S;
	nBufferSize   : UDINT := 512;
	nEstoqueMax   : INT   := 999;
	bValid        : BOOL  := FALSE;   // TRUE após FB_DfiConfigLoader parsear o arquivo com sucesso
END_STRUCT
END_TYPE
]]></Declaration>
  </DUT>
</TcPlcObject>
```

- [ ] **Step 6: `ST_DfiDiag.TcDUT`** (spec §10)

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <DUT Name="ST_DfiDiag" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[TYPE ST_DfiDiag :
STRUCT
	bConfigOk         : BOOL;
	bMqttConnected    : BOOL;
	bDbConnected      : BOOL;
	nReconnectCount   : UDINT;
	nBufferCount      : UDINT;
	nBufferHighWater  : UDINT;
	nBufferDropped    : ULINT;
	nRowsWritten      : ULINT;
	nDbErrors         : ULINT;
	nParseErrors      : ULINT;
	sUltimoParseError : STRING(120);
	sUltimoDbError    : STRING(255);
	eWriterState      : E_DfiWriterState;
END_STRUCT
END_TYPE
]]></Declaration>
  </DUT>
</TcPlcObject>
```

- [ ] **Step 7: `GVL_Dfi.TcGVL`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <GVL Name="GVL_Dfi" Id="{GENERATE-NEW-GUID}">
    <Declaration><![CDATA[{attribute 'qualified_only'}
VAR_GLOBAL
	gCfg  : ST_DfiConfig;
	gDiag : ST_DfiDiag;
END_VAR
]]></Declaration>
  </GVL>
</TcPlcObject>
```

- [ ] **Step 8: Register the new files in `PLC.plcproj`**

Add a `<Compile Include="...">` entry for each new `.TcDUT` / `.TcGVL` under the appropriate `<ItemGroup>` (mirror how `DatabaseServer1` lists `DUTs\ST_VALORES.TcDUT`). Path separators in `.plcproj` are `\`.

- [ ] **Step 9: ⛳ CHECKPOINT (human) — build**

*Build Solution*. Expected: **0 errors**. All DUTs and the GVL appear in the project tree.

- [ ] **Step 10: Commit**

```bash
git add "Banco-de-Dados/CX9240_DataFlowInventory/TwinCAT Project"
git commit -m "feat: DUTs and GVL for CX9240 historian" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `FB_DfiRowBuffer` (FIFO) + TcUnit wiring

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiRowBuffer.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/test/PRG_DfiTests.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/test/FB_DfiRowBuffer_Tests.TcPOU`
- Modify: `TwinCAT Project/PLC/PLC.plcproj` (add TcUnit reference + register files)
- Modify: `TwinCAT Project.tsproj` (add a second `PlcTask` `TestTask` that calls `PRG_DfiTests`, or reuse the main task — see Step 2)

**Interfaces:**
- Consumes: `ST_DfiRow`, `E_DfiRowKind` (Task 4).
- Produces:
  - `FB_DfiRowBuffer` with `VAR_INPUT nCapacity : UDINT := 512; END_VAR`, `VAR_OUTPUT nCount : UDINT; nHighWater : UDINT; nDropped : ULINT; END_VAR`
  - `METHOD Push : BOOL` — `VAR_INPUT stRow : ST_DfiRow; END_VAR` — returns TRUE on clean enqueue, FALSE if it overwrote the oldest (still enqueues the new row).
  - `METHOD Peek : BOOL` — `VAR_OUTPUT stRow : ST_DfiRow; END_VAR` — FALSE if empty.
  - `METHOD Pop : BOOL` — no params — removes the front; FALSE if empty.
  - Body-call `FB_DfiRowBuffer()` recomputes `nCount` each cycle (so the FB must be called cyclically OR the methods keep `nCount` current — implement methods to keep counters current, and make the FB body a no-op).

- [ ] **Step 1: Add TcUnit reference**

In `PLC.plcproj` add a library reference to `TcUnit` (`* (www.tcunit.org)`), same `<ItemGroup>` shape as the other refs. Install the TcUnit package in XAE if not present (human, at checkpoint).

- [ ] **Step 2: Write `PRG_DfiTests.TcPOU`** (TcUnit runner)

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="PRG_DfiTests" Id="{GENERATE-NEW-GUID}" SpecialFunc="None">
    <Declaration><![CDATA[PROGRAM PRG_DfiTests
VAR
	fbRowBufferTests : FB_DfiRowBuffer_Tests;
	// suites added by later tasks:
	// fbSamplerTests   : FB_DfiSampler_Tests;
	// fbCfgParseTests  : FB_DfiCfgParse_Tests;
	// fbParserTests    : FB_DfiPayloadParser_Tests;
	// fbSqlBuilderTests: FB_DfiSqlBuilder_Tests;
END_VAR
]]></Declaration>
    <Implementation>
      <ST><![CDATA[TcUnit.RUN();]]></ST>
    </Implementation>
  </POU>
</TcPlcObject>
```

Register `PRG_DfiTests` on a PLC task. Simplest: add a `<Task>` named `TestTask` (priority just below `PlcTask`, 100 ms, AutoStart TRUE) and reference `PRG_DfiTests`. Mark the `test/` folder to be **excluded from the boot project** for production builds (in XAE: right-click folder → *Properties → Build → Exclude from build* toggled per configuration; document this toggle in `comissionamento-rt-linux.md`).

- [ ] **Step 3: Write the failing test suite `FB_DfiRowBuffer_Tests.TcPOU`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_DfiRowBuffer_Tests" Id="{GENERATE-NEW-GUID}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_DfiRowBuffer_Tests EXTENDS TcUnit.FB_TestSuite
VAR
END_VAR
]]></Declaration>
    <Implementation>
      <ST><![CDATA[Test_PushPop_PreservaOrdemFIFO();
Test_Peek_NaoRemove();
Test_PopVazio_RetornaFalse();
Test_Overflow_DescartaMaisAntigo_IncrementaDropped();
Test_HighWater_AcompanhaPico();
]]></ST>
    </Implementation>
  </POU>
</TcPlcObject>
```

Add these methods to the same POU file as `<Method>` elements (TcUnit style). Method bodies:

```pascal
METHOD PRIVATE Test_PushPop_PreservaOrdemFIFO
VAR
	fb : FB_DfiRowBuffer := (nCapacity := 4);
	a, b, out : ST_DfiRow;
BEGIN
	TEST('PushPop_PreservaOrdemFIFO');
	a.eKind := E_DfiRowKind.EVENTO; a.stEvento.sEvento := 'entrega';
	b.eKind := E_DfiRowKind.EVENTO; b.stEvento.sEvento := 'erro';
	fb.Push(a); fb.Push(b);
	AssertEquals_UDINT(Expected := 2, Actual := fb.nCount, Message := 'nCount apos 2 Push');
	fb.Peek(out); fb.Pop();
	AssertEquals_STRING(Expected := 'entrega', Actual := out.stEvento.sEvento, Message := '1o a sair');
	fb.Peek(out); fb.Pop();
	AssertEquals_STRING(Expected := 'erro', Actual := out.stEvento.sEvento, Message := '2o a sair');
	AssertEquals_UDINT(Expected := 0, Actual := fb.nCount, Message := 'vazio ao final');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Peek_NaoRemove
VAR
	fb : FB_DfiRowBuffer := (nCapacity := 4);
	a, out : ST_DfiRow;
	ok : BOOL;
BEGIN
	TEST('Peek_NaoRemove');
	a.eKind := E_DfiRowKind.ESTOQUE_MUDANCA; a.stEstoque.nA := 7;
	fb.Push(a);
	ok := fb.Peek(out);
	AssertTrue(ok, 'Peek TRUE com 1 item');
	AssertEquals_INT(Expected := 7, Actual := out.stEstoque.nA, Message := 'valor via Peek');
	AssertEquals_UDINT(Expected := 1, Actual := fb.nCount, Message := 'Peek nao remove');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_PopVazio_RetornaFalse
VAR
	fb : FB_DfiRowBuffer := (nCapacity := 4);
	out : ST_DfiRow;
BEGIN
	TEST('PopVazio_RetornaFalse');
	AssertFalse(fb.Peek(out), 'Peek FALSE vazio');
	AssertFalse(fb.Pop(), 'Pop FALSE vazio');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Overflow_DescartaMaisAntigo_IncrementaDropped
VAR
	fb : FB_DfiRowBuffer := (nCapacity := 3);
	r, out : ST_DfiRow;
	i : INT;
	okPush : BOOL;
BEGIN
	TEST('Overflow_DescartaMaisAntigo_IncrementaDropped');
	FOR i := 1 TO 3 DO
		r.stEstoque.nA := i; fb.Push(r);
	END_FOR
	r.stEstoque.nA := 4;
	okPush := fb.Push(r);                       // capacidade estourada
	AssertFalse(okPush, 'Push retorna FALSE ao descartar');
	AssertEquals_ULINT(Expected := 1, Actual := fb.nDropped, Message := 'nDropped incrementa');
	AssertEquals_UDINT(Expected := 3, Actual := fb.nCount, Message := 'nCount fica no teto');
	fb.Peek(out);
	AssertEquals_INT(Expected := 2, Actual := out.stEstoque.nA, Message := 'frente agora eh o 2o (1o descartado)');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_HighWater_AcompanhaPico
VAR
	fb : FB_DfiRowBuffer := (nCapacity := 8);
	r : ST_DfiRow;
	i : INT;
BEGIN
	TEST('HighWater_AcompanhaPico');
	FOR i := 1 TO 5 DO fb.Push(r); END_FOR
	fb.Pop(); fb.Pop();
	AssertEquals_UDINT(Expected := 3, Actual := fb.nCount, Message := 'nCount 3 apos 2 Pop');
	AssertEquals_UDINT(Expected := 5, Actual := fb.nHighWater, Message := 'highwater guarda o pico 5');
	TEST_FINISHED();
END_METHOD
```

- [ ] **Step 4: ⛳ CHECKPOINT (human) — run tests, expect FAIL**

Activate config on a runtime, log in, run. Expected TcUnit output: `FB_DfiRowBuffer` type not found → build error (RED). This confirms the tests reference the not-yet-written FB.

- [ ] **Step 5: Write `FB_DfiRowBuffer.TcPOU`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<TcPlcObject Version="1.1.0.1">
  <POU Name="FB_DfiRowBuffer" Id="{GENERATE-NEW-GUID}" SpecialFunc="None">
    <Declaration><![CDATA[FUNCTION_BLOCK FB_DfiRowBuffer
VAR_INPUT
	nCapacity : UDINT := 512;
END_VAR
VAR_OUTPUT
	nCount     : UDINT;
	nHighWater : UDINT;
	nDropped   : ULINT;
END_VAR
VAR CONSTANT
	MAX_ROWS : UDINT := 512;   // teto físico do array; nCapacity <= MAX_ROWS
END_VAR
VAR
	aRows  : ARRAY[0..MAX_ROWS-1] OF ST_DfiRow;
	nHead  : UDINT;            // índice de leitura (frente)
	nTail  : UDINT;            // índice de escrita (próxima posição livre)
	nCap   : UDINT;            // capacidade efetiva (clamp de nCapacity)
	bInit  : BOOL;
END_VAR
]]></Declaration>
    <Implementation>
      <ST><![CDATA[IF NOT bInit THEN
	nCap := LIMIT(1, nCapacity, MAX_ROWS);
	bInit := TRUE;
END_IF
// nCount é mantido pelos métodos; corpo do FB é no-op.
]]></ST>
    </Implementation>
  </POU>
</TcPlcObject>
```

Methods (add as `<Method>` elements):

```pascal
METHOD Push : BOOL
VAR_INPUT
	stRow : ST_DfiRow;
END_VAR
VAR
	bClean : BOOL;
BEGIN
	IF NOT bInit THEN nCap := LIMIT(1, nCapacity, MAX_ROWS); bInit := TRUE; END_IF
	bClean := TRUE;
	IF nCount >= nCap THEN
		// buffer cheio: descarta o mais antigo
		nHead := (nHead + 1) MOD nCap;
		nCount := nCount - 1;
		nDropped := nDropped + 1;
		bClean := FALSE;
	END_IF
	aRows[nTail] := stRow;
	nTail := (nTail + 1) MOD nCap;
	nCount := nCount + 1;
	IF nCount > nHighWater THEN nHighWater := nCount; END_IF
	Push := bClean;
END_METHOD
```

```pascal
METHOD Peek : BOOL
VAR_OUTPUT
	stRow : ST_DfiRow;
END_VAR
BEGIN
	IF nCount = 0 THEN
		Peek := FALSE;
		RETURN;
	END_IF
	stRow := aRows[nHead];
	Peek := TRUE;
END_METHOD
```

```pascal
METHOD Pop : BOOL
BEGIN
	IF nCount = 0 THEN
		Pop := FALSE;
		RETURN;
	END_IF
	nHead := (nHead + 1) MOD nCap;
	nCount := nCount - 1;
	Pop := TRUE;
END_METHOD
```

- [ ] **Step 6: ⛳ CHECKPOINT (human) — run tests, expect PASS**

Expected TcUnit output: suite `FB_DfiRowBuffer_Tests`, 5 tests, **0 failures**.

- [ ] **Step 7: Commit**

```bash
git add "Banco-de-Dados/CX9240_DataFlowInventory/TwinCAT Project"
git commit -m "feat: FB_DfiRowBuffer FIFO with TcUnit suite" -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: `FB_DfiSampler` (periodic snapshot) + tests

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiSampler.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/test/FB_DfiSampler_Tests.TcPOU`
- Modify: `PRG_DfiTests.TcPOU` (instantiate `fbSamplerTests`), `PLC.plcproj` (register files)

**Interfaces:**
- Consumes: `ST_EstoqueSnapshot`, `ST_DfiRow`, `E_DfiRowKind`, `FB_DfiRowBuffer` (Push).
- Produces: `FB_DfiSampler` with
  `VAR_INPUT stUltimoEstoque : ST_EstoqueSnapshot; bValido : BOOL; tPeriodo : TIME; END_VAR`
  `VAR_IN_OUT fbBuffer : FB_DfiRowBuffer; END_VAR`
  `VAR_OUTPUT nPushed : ULINT; END_VAR`
  On each `tPeriodo` elapse, if `bValido`, `Push` an `ST_DfiRow` with `eKind := ESTOQUE_PERIODICO`, `stEstoque := stUltimoEstoque`, `sTsPlc := <now>`.

- [ ] **Step 1: Write failing suite `FB_DfiSampler_Tests.TcPOU`**

Suite body calls: `Test_NaoDispara_SemEstoqueValido()`, `Test_Dispara_ AposPeriodo_ComUltimoEstoque()`, `Test_Rearma_ACadaPeriodo()`.

```pascal
METHOD PRIVATE Test_NaoDispara_SemEstoqueValido
VAR
	fbBuf : FB_DfiRowBuffer := (nCapacity := 8);
	fbSut : FB_DfiSampler;
	est   : ST_EstoqueSnapshot;
	i     : INT;
BEGIN
	TEST('NaoDispara_SemEstoqueValido');
	FOR i := 1 TO 50 DO
		fbSut(stUltimoEstoque := est, bValido := FALSE, tPeriodo := T#100MS, fbBuffer := fbBuf);
	END_FOR
	AssertEquals_UDINT(Expected := 0, Actual := fbBuf.nCount, Message := 'nada empurrado sem estoque valido');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Dispara_AposPeriodo_ComUltimoEstoque
VAR
	fbBuf : FB_DfiRowBuffer := (nCapacity := 8);
	fbSut : FB_DfiSampler;
	est   : ST_EstoqueSnapshot;
	out   : ST_DfiRow;
BEGIN
	TEST('Dispara_AposPeriodo_ComUltimoEstoque');
	est.nA := 3; est.nB := 4; est.nC := 5;
	// simula passagem de tempo: TcUnit roda em ciclos; usa CycleCallCount + tPeriodo curto
	fbSut(stUltimoEstoque := est, bValido := TRUE, tPeriodo := T#20MS, fbBuffer := fbBuf);
	// esperar o TON: chamar o SUT em ciclos sucessivos até nCount = 1 ou timeout do teste
	// (TcUnit avança o tempo real entre ciclos da task de teste)
	IF fbBuf.nCount >= 1 THEN
		fbBuf.Peek(out);
		AssertEquals_INT(Expected := 3, Actual := out.stEstoque.nA, Message := 'snapshot A');
		AssertTrue(out.eKind = E_DfiRowKind.ESTOQUE_PERIODICO, 'eKind periodico');
		TEST_FINISHED();
	END_IF
END_METHOD
```

> Note for the implementer: TcUnit test methods re-run every task cycle until `TEST_FINISHED()`. Time-based tests use a short `tPeriodo` and simply wait for the condition across cycles (the pattern above). If TcUnit's `FB_TestSuite` timeout is hit first the test fails — set the suite/global TcUnit timeout ≥ 2 s in `PRG_DfiTests` config.

`Test_Rearma_ACadaPeriodo`: after the first push, keep calling; assert `fbBuf.nCount` reaches 2 then 3 at roughly `tPeriodo` spacing (assert `>= 2` after enough cycles; exact timing not asserted).

- [ ] **Step 2: ⛳ CHECKPOINT (human) — expect FAIL** (`FB_DfiSampler` undefined).

- [ ] **Step 3: Write `FB_DfiSampler.TcPOU`**

```pascal
FUNCTION_BLOCK FB_DfiSampler
VAR_INPUT
	stUltimoEstoque : ST_EstoqueSnapshot;
	bValido         : BOOL;
	tPeriodo        : TIME;
END_VAR
VAR_IN_OUT
	fbBuffer : FB_DfiRowBuffer;
END_VAR
VAR_OUTPUT
	nPushed : ULINT;
END_VAR
VAR
	fbTon : TON;
	row   : ST_DfiRow;
END_VAR
// -----
fbTon(IN := bValido, PT := tPeriodo);
IF fbTon.Q THEN
	fbTon(IN := FALSE);           // rearma
	row.eKind := E_DfiRowKind.ESTOQUE_PERIODICO;
	row.stEstoque := stUltimoEstoque;
	row.sTsPlc := F_DfiNowString();   // helper da Task 10, ver nota
	fbBuffer.Push(row);
	nPushed := nPushed + 1;
END_IF
```

> `F_DfiNowString()` (returns `STRING(23)` `'YYYY-MM-DD HH:MM:SS.mmm'`) is defined in Task 10 as a standalone FUNCTION. Until Task 10 lands, stub it in this task as a FUNCTION returning `'1970-01-01 00:00:00.000'` and replace the stub in Task 10. Add a `- [ ]` sub-note to Task 10 Step "replace the F_DfiNowString stub".

- [ ] **Step 4: ⛳ CHECKPOINT (human) — expect PASS** (3 tests).

- [ ] **Step 5: Commit** `feat: FB_DfiSampler periodic stock snapshot with tests`

---

## Task 7: `FB_DfiCfgParse` + `FB_DfiConfigLoader` + tests

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiCfgParse.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiConfigLoader.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/test/FB_DfiCfgParse_Tests.TcPOU`
- Modify: `PRG_DfiTests.TcPOU`, `PLC.plcproj`

**Interfaces:**
- Consumes: `ST_DfiConfig` (Task 4).
- Produces:
  - `METHOD FB_DfiCfgParse.ParseLine : BOOL` — `VAR_INPUT sLine : STRING(255); END_VAR VAR_IN_OUT stCfg : ST_DfiConfig; END_VAR` — parses one `key=value` line into `stCfg`; returns FALSE on an unrecognised key or malformed value (comment/blank lines return TRUE, no-op).
  - `METHOD FB_DfiCfgParse.ParseText : BOOL` — `VAR_INPUT sText : STRING(4095); END_VAR VAR_IN_OUT stCfg : ST_DfiConfig; END_VAR` — splits on line breaks, calls `ParseLine` per line, sets `stCfg.bValid := TRUE` only if `sMqttHost <> ''` and every non-blank line parsed.
  - `FB_DfiConfigLoader` with `VAR_INPUT bExecute : BOOL; sPath : STRING(255) := '/etc/dfi/historian.conf'; END_VAR VAR_OUTPUT bDone, bError : BOOL; stCfg : ST_DfiConfig; sError : STRING(120); END_VAR` — reads the file with `Tc2_System.FB_FileOpen`/`FB_FileGets`/`FB_FileClose`, feeds `ParseText`.

- [ ] **Step 1: Write failing suite `FB_DfiCfgParse_Tests.TcPOU`**

```pascal
METHOD PRIVATE Test_ParseLine_MapeiaChavesConhecidas
VAR
	fb  : FB_DfiCfgParse;
	cfg : ST_DfiConfig;
BEGIN
	TEST('ParseLine_MapeiaChavesConhecidas');
	fb.ParseLine('mqtt_host=10.0.0.5', cfg);
	fb.ParseLine('mqtt_port=8883', cfg);
	fb.ParseLine('mqtt_use_tls=1', cfg);
	fb.ParseLine('sample_period_s=30', cfg);
	fb.ParseLine('buffer_size=256', cfg);
	fb.ParseLine('estoque_max=50', cfg);
	AssertEquals_STRING(Expected := '10.0.0.5', Actual := cfg.sMqttHost, Message := 'host');
	AssertEquals_UINT(Expected := 8883, Actual := cfg.nMqttPort, Message := 'port');
	AssertTrue(cfg.bUseTls, 'tls');
	AssertTrue(cfg.tSamplePeriod = T#30S, 'periodo');
	AssertEquals_UDINT(Expected := 256, Actual := cfg.nBufferSize, Message := 'buffer');
	AssertEquals_INT(Expected := 50, Actual := cfg.nEstoqueMax, Message := 'estoque_max');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_ParseLine_ComentarioEBranco_NoOp
VAR
	fb  : FB_DfiCfgParse;
	cfg : ST_DfiConfig;
BEGIN
	TEST('ParseLine_ComentarioEBranco_NoOp');
	AssertTrue(fb.ParseLine('# comentario', cfg), 'comentario ok');
	AssertTrue(fb.ParseLine('', cfg), 'linha vazia ok');
	AssertTrue(fb.ParseLine('   ', cfg), 'espacos ok');
	AssertEquals_STRING(Expected := '', Actual := cfg.sMqttHost, Message := 'nada mudou');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_ParseLine_ChaveDesconhecida_RetornaFalse
VAR
	fb  : FB_DfiCfgParse;
	cfg : ST_DfiConfig;
BEGIN
	TEST('ParseLine_ChaveDesconhecida_RetornaFalse');
	AssertFalse(fb.ParseLine('foo=bar', cfg), 'chave desconhecida => FALSE');
	AssertFalse(fb.ParseLine('mqtt_port=abc', cfg), 'valor nao-numerico => FALSE');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_ParseText_ExemploCompleto_ValidaEbValidTrue
VAR
	fb  : FB_DfiCfgParse;
	cfg : ST_DfiConfig;
	s   : STRING(4095);
BEGIN
	TEST('ParseText_ExemploCompleto');
	s := CONCAT('mqtt_host=192.168.0.50$N', CONCAT('mqtt_port=1883$N', CONCAT('topic_estoque=dataflow/estoque$N', 'db_id=1$N')));
	AssertTrue(fb.ParseText(s, cfg), 'ParseText ok');
	AssertTrue(cfg.bValid, 'bValid TRUE com host preenchido');
	AssertEquals_STRING(Expected := 'dataflow/estoque', Actual := cfg.sTopicEstoque, Message := 'topico');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_ParseText_SemHost_bValidFalse
VAR
	fb  : FB_DfiCfgParse;
	cfg : ST_DfiConfig;
BEGIN
	TEST('ParseText_SemHost_bValidFalse');
	fb.ParseText('mqtt_port=1883$Ndb_id=1', cfg);
	AssertFalse(cfg.bValid, 'sem host => invalido');
	TEST_FINISHED();
END_METHOD
```

- [ ] **Step 2: ⛳ CHECKPOINT (human) — expect FAIL.**

- [ ] **Step 3: Write `FB_DfiCfgParse.TcPOU`**

Declaration: `FUNCTION_BLOCK FB_DfiCfgParse` (no VAR needed).

`ParseLine` implementation outline (write in full):
- Trim leading/trailing spaces/tabs (`Tc2_Standard`/string funcs; use `DELETE`/`FIND`/`LEN` or `Tc2_Utilities.Trim` if available — implement a local trim if not).
- If `LEN = 0` or first char is `#` → `ParseLine := TRUE; RETURN;`.
- Find `=` via `FIND(sLine, '=')`; if 0 → `ParseLine := FALSE; RETURN;`.
- `sKey := LEFT(...); sVal := RIGHT(...)`; trim both.
- `CASE sKey OF` (string CASE not allowed in ST — use `IF sKey = 'mqtt_host' THEN ... ELSIF ...`):
  - `mqtt_host` → `stCfg.sMqttHost := sVal;`
  - `mqtt_port` → `STRING_TO_UINT` guarded (validate all chars digits first; else FALSE)
  - `mqtt_use_tls` → `stCfg.bUseTls := (sVal = '1');`
  - `mqtt_ca_cert_path` → `stCfg.sCaCertPath := sVal;`
  - `mqtt_user` → `stCfg.sMqttUser := sVal;`
  - `mqtt_pass` → `stCfg.sMqttPass := sVal;`
  - `topic_estoque` → `stCfg.sTopicEstoque := sVal;`
  - `topic_eventos` → `stCfg.sTopicEventos := sVal;`
  - `db_id` → digits → `STRING_TO_UDINT`
  - `sample_period_s` → digits → `stCfg.tSamplePeriod := UDINT_TO_TIME(STRING_TO_UDINT(sVal) * 1000);`
  - `buffer_size` → digits → `STRING_TO_UDINT`, clamp `1..512`
  - `estoque_max` → digits → `STRING_TO_INT`
  - else → `ParseLine := FALSE; RETURN;`
- `ParseLine := TRUE;`

`ParseText`: reset a local `bAllOk := TRUE`; iterate splitting on `$N` (LF) and `$R` (CR) — use repeated `FIND` + `LEFT`/`RIGHT`. For each line, `IF NOT ParseLine(line, stCfg) THEN bAllOk := FALSE; END_IF`. At end: `stCfg.bValid := bAllOk AND (stCfg.sMqttHost <> '');` `ParseText := bAllOk;`.

- [ ] **Step 4: Write `FB_DfiConfigLoader.TcPOU`**

State machine using `Tc2_System` file FBs:
- `0 IDLE`: on rising `bExecute` → `bDone := FALSE; bError := FALSE;` → `10`.
- `10 OPEN`: `FB_FileOpen(sPathName := sPath, nMode := FOPEN_MODEREAD OR FOPEN_MODETEXT, ...)`; done → `20`; error → set `sError := 'open'`, `bError := TRUE` → `90`.
- `20 READ`: loop `FB_FileGets` accumulating into `sText : STRING(4095)` with `$N` between lines until `bEOF`; guard overflow (`LEN(sText) > 4000` → stop, `sError := 'file too big'`, `bError` → `90`).
- `30 CLOSE`: `FB_FileClose`.
- `40 PARSE`: `fbParse.ParseText(sText, stCfg)`; if `NOT stCfg.bValid` → `sError := 'parse/host'`, `bError := TRUE`. `bDone := TRUE;` → `0`.
- `90 ERR`: ensure file closed; `bDone := TRUE;` → `0`.

- [ ] **Step 5: ⛳ CHECKPOINT (human) — `FB_DfiCfgParse_Tests` PASS (5 tests).** `FB_DfiConfigLoader` is exercised later on hardware (Task 15 bench).

- [ ] **Step 6: Commit** `feat: config file parser + loader (historian.conf) with tests`

---

## Task 8: `FB_DfiPayloadParser` + tests

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiPayloadParser.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/fb/F_DfiSanitizeText.TcPOU` (FUNCTION)
- Create: `TwinCAT Project/PLC/POUs/test/FB_DfiPayloadParser_Tests.TcPOU`
- Modify: `PRG_DfiTests.TcPOU`, `PLC.plcproj`

**Interfaces:**
- Consumes: `ST_EstoqueSnapshot`, `ST_EventoDfi`, `E_DfiRowKind`, `ST_DfiConfig`, `Tc3_JsonXml.FB_JsonDomParser`.
- Produces:
  - `FUNCTION F_DfiSanitizeText : BOOL` — `VAR_INPUT sIn : STRING(254); nMaxLen : INT; END_VAR VAR_OUTPUT sOut : STRING(254); END_VAR` — returns TRUE if every char of `sIn` is in `[A-Za-z0-9_ -]`; copies (truncated to `nMaxLen`) into `sOut`. FALSE ⇒ caller rejects the row; `sOut` undefined.
  - `FB_DfiPayloadParser` with
    `VAR_INPUT sTopic : STRING(255); sPayload : STRING(510); stConfig : ST_DfiConfig; bExecute : BOOL; END_VAR`
    `VAR_OUTPUT bDone : BOOL; bOk : BOOL; eKind : E_DfiRowKind; stEstoque : ST_EstoqueSnapshot; stEvento : ST_EventoDfi; sParseError : STRING(120); END_VAR`
  - `bOk = TRUE` ⇒ exactly one of `stEstoque` / `stEvento` populated per `eKind` (`ESTOQUE_MUDANCA` or `EVENTO`).

- [ ] **Step 1: Write failing suite `FB_DfiPayloadParser_Tests.TcPOU`**

Cases (each its own `TEST(...)`), payloads use `$'` for embedded quotes:

```pascal
METHOD PRIVATE Test_Estoque_Valido
VAR fb : FB_DfiPayloadParser; cfg : ST_DfiConfig; BEGIN
	TEST('Estoque_Valido');
	cfg.sTopicEstoque := 'dataflow/estoque'; cfg.nEstoqueMax := 999;
	fb(bExecute := TRUE, sTopic := 'dataflow/estoque',
	   sPayload := '{"type":"estoque","pecaA":4,"pecaB":5,"pecaC":6}', stConfig := cfg);
	AssertTrue(fb.bOk, 'bOk');
	AssertTrue(fb.eKind = E_DfiRowKind.ESTOQUE_MUDANCA, 'eKind');
	AssertEquals_INT(4, fb.stEstoque.nA, 'A'); AssertEquals_INT(5, fb.stEstoque.nB, 'B'); AssertEquals_INT(6, fb.stEstoque.nC, 'C');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Evento_Entrega
VAR fb : FB_DfiPayloadParser; cfg : ST_DfiConfig; BEGIN
	TEST('Evento_Entrega');
	cfg.sTopicEventos := 'dataflow/eventos';
	fb(bExecute := TRUE, sTopic := 'dataflow/eventos',
	   sPayload := '{"type":"evento","evento":"entrega","peca":"A"}', stConfig := cfg);
	AssertTrue(fb.bOk, 'bOk');
	AssertTrue(fb.eKind = E_DfiRowKind.EVENTO, 'eKind');
	AssertEquals_STRING('entrega', fb.stEvento.sEvento, 'evento');
	AssertEquals_STRING('A', fb.stEvento.sPeca, 'peca');
	AssertEquals_STRING('', fb.stEvento.sDetalhe, 'sem detalhe');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Evento_ErroTimeout_MapeiaTipoParaDetalhe
VAR fb : FB_DfiPayloadParser; cfg : ST_DfiConfig; BEGIN
	TEST('Evento_ErroTimeout');
	cfg.sTopicEventos := 'dataflow/eventos';
	fb(bExecute := TRUE, sTopic := 'dataflow/eventos',
	   sPayload := '{"type":"evento","evento":"erro","tipo":"timeout","peca":"B"}', stConfig := cfg);
	AssertTrue(fb.bOk, 'bOk');
	AssertEquals_STRING('erro', fb.stEvento.sEvento, 'evento');
	AssertEquals_STRING('timeout', fb.stEvento.sDetalhe, 'tipo -> detalhe');
	AssertEquals_STRING('B', fb.stEvento.sPeca, 'peca');
	TEST_FINISHED();
END_METHOD
```

Remaining cases — full method bodies following the same shape:
- `Test_JsonInvalido_bOkFalse` — `sPayload := '{not json'` → `bOk=FALSE`, `sParseError='json'`.
- `Test_TypeAusente_bOkFalse` — `'{"pecaA":1}'` → `sParseError='type'`.
- `Test_TypeDesconhecido_bOkFalse` — `'{"type":"sensores",...}'` → `sParseError='type'`.
- `Test_Estoque_CampoFaltando_bOkFalse` — `'{"type":"estoque","pecaA":1,"pecaB":2}'` → `sParseError='campo'`.
- `Test_Estoque_Negativo_bOkFalse` — `pecaA:-1` → `sParseError='faixa'`.
- `Test_Estoque_AcimaDoMax_bOkFalse` — `cfg.nEstoqueMax := 10`, `pecaC:11` → `sParseError='faixa'`.
- `Test_Evento_SemCampoEvento_bOkFalse` — `'{"type":"evento","peca":"A"}'` → `sParseError='campo'`.
- `Test_Evento_PecaInvalida_bOkFalse` — `"peca":"D"` → `sParseError='peca'`.
- `Test_Evento_PecaAusente_Ok_PecaVazia` — `'{"type":"evento","evento":"inicializacao"}'` → `bOk=TRUE`, `sPeca=''`.
- `Test_Evento_DetalheComAspa_bOkFalse` — `"tipo":"ti'meout"` → `sParseError='sanit'`.
- `Test_Evento_EventoComPontoEVirgula_bOkFalse` — `"evento":"a;b"` → `sParseError='sanit'`.
- `Test_Evento_DetalheLongo_Truncado` — `tipo` = 80 chars of `x` → `bOk=TRUE`, `LEN(fb.stEvento.sDetalhe) = 63`.
- `Test_Evento_PayloadRaw_Preenchido` — assert `fb.stEvento.sPayloadRaw` starts with `{"type":"evento"` and `LEN <= 254`.
- `Test_TopicoDesconhecido_bOkFalse` — `sTopic := 'dataflow/sensores'` → `sParseError='topic'`.

- [ ] **Step 2: ⛳ CHECKPOINT (human) — expect FAIL.**

- [ ] **Step 3: Write `F_DfiSanitizeText.TcPOU`**

```pascal
FUNCTION F_DfiSanitizeText : BOOL
VAR_INPUT
	sIn     : STRING(254);
	nMaxLen : INT;
END_VAR
VAR_OUTPUT
	sOut : STRING(254);
END_VAR
VAR
	i, n : INT;
	c    : BYTE;
	p    : POINTER TO BYTE;
END_VAR
// -----
n := LEN(sIn);
p := ADR(sIn);
FOR i := 0 TO n - 1 DO
	c := p[i];
	IF NOT ( (c >= 65 AND c <= 90)  OR   // A-Z
	         (c >= 97 AND c <= 122) OR   // a-z
	         (c >= 48 AND c <= 57)  OR   // 0-9
	         (c = 32) OR (c = 95) OR (c = 45) ) THEN  // space _ -
		F_DfiSanitizeText := FALSE;
		RETURN;
	END_IF
END_FOR
IF n > nMaxLen THEN
	sOut := LEFT(sIn, nMaxLen);
ELSE
	sOut := sIn;
END_IF
F_DfiSanitizeText := TRUE;
```

- [ ] **Step 4: Write `FB_DfiPayloadParser.TcPOU`**

Declaration includes `fbJson : Tc3_JsonXml.FB_JsonDomParser;` and locals. Implementation on rising `bExecute`:
1. `bDone := FALSE; bOk := FALSE; sParseError := '';` clear `stEstoque`/`stEvento`.
2. Topic routing: if `sTopic = stConfig.sTopicEstoque` → expect estoque; elif `sTopic = stConfig.sTopicEventos` → expect evento; else `sParseError := 'topic'` → done.
3. `IF NOT fbJson.ParseDocument(sPayload) THEN sParseError := 'json'; done. END_IF` (use the exact TF6020 method name from the installed lib — `ParseDocument` / `Parse`; confirm on the box).
4. Get root; read `sType := <get string member 'type'>`. If missing/empty → `sParseError := 'type'`. If not the expected value for the topic → `sParseError := 'type'`.
5. **Estoque branch:** read int members `pecaA`,`pecaB`,`pecaC`. Missing/not-int → `sParseError := 'campo'`. Range check `0 .. stConfig.nEstoqueMax` → else `sParseError := 'faixa'`. On success `eKind := ESTOQUE_MUDANCA`, fill `stEstoque`, `bOk := TRUE`.
6. **Evento branch:**
   - `sEv := <string 'evento'>`. Empty/missing → `sParseError := 'campo'`.
   - `IF NOT F_DfiSanitizeText(sEv, 23, sEvClean) THEN sParseError := 'sanit'; done. END_IF`
   - `peca`: if member present → must be exactly `'A'|'B'|'C'` else `sParseError := 'peca'`; if absent → `sPeca := ''`.
   - `tipo`: if present → `F_DfiSanitizeText(sTipo, 63, sDetClean)`; FALSE → `sParseError := 'sanit'`. Absent → `sDetalhe := ''`.
   - `sPayloadRaw`: `F_DfiSanitizeText(LEFT(sPayload,254), 254, sRaw)`; **on FALSE here, do not reject** — set `sPayloadRaw := ''` (raw is audit-only, best-effort). (Design note: only `evento`/`detalhe` rejection blocks the row.)
   - Fill `stEvento`, `eKind := EVENTO`, `bOk := TRUE`.
7. `bDone := TRUE;`

> If the raw payload contains characters outside the allowlist (it will — braces, quotes, colons), `F_DfiSanitizeText` returns FALSE for `sPayloadRaw`. That is expected; per step 6 we swallow it and store `''`. **Do not** gate the row on `payload_raw`. Only `evento` and `detalhe` gate. Update `Test_Evento_PayloadRaw_Preenchido` to assert `sPayloadRaw = ''` for a normal JSON payload — OR change `F_DfiSanitizeText` usage for raw to a lighter filter that only strips `'`,`"`,`;`,`\`,backtick and keeps the rest. **Decision: lighter filter for raw.** Add `F_DfiStripSqlUnsafe : STRING(254)` (removes only `' " ; \ backtick` and bytes < 0x20, keeps everything else) and use it for `sPayloadRaw`. Add one test `Test_StripSqlUnsafe_RemoveAspas`.

- [ ] **Step 5: Add `F_DfiStripSqlUnsafe.TcPOU`** per the decision above; body: copy input to output skipping bytes `39 (') / 34 (") / 59 (;) / 92 (\) / 96 (backtick)` and any `< 32`; cap at 254.

- [ ] **Step 6: ⛳ CHECKPOINT (human) — expect PASS** (~19 tests).

- [ ] **Step 7: Commit** `feat: FB_DfiPayloadParser (JSON -> struct, validate, sanitize) with tests`

---

## Task 9: `FB_DfiSqlBuilder` + tests

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiSqlBuilder.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/test/FB_DfiSqlBuilder_Tests.TcPOU`
- Modify: `PRG_DfiTests.TcPOU`, `PLC.plcproj`

**Interfaces:**
- Consumes: `ST_DfiRow`, `E_DfiRowKind`, `Tc2_Utilities.FB_FormatString`, `F_String`, `F_INT`.
- Produces: `METHOD FB_DfiSqlBuilder.Build : BOOL` — `VAR_INPUT stRow : ST_DfiRow; END_VAR VAR_OUTPUT sCmd : STRING(511); END_VAR` — writes the exact INSERT statement for the row's `eKind`. Returns FALSE only if `FB_FormatString` errors.

- [ ] **Step 1: Write failing suite `FB_DfiSqlBuilder_Tests.TcPOU`**

```pascal
METHOD PRIVATE Test_Build_EstoqueMudanca
VAR fb : FB_DfiSqlBuilder; r : ST_DfiRow; s : STRING(511); BEGIN
	TEST('Build_EstoqueMudanca');
	r.eKind := E_DfiRowKind.ESTOQUE_MUDANCA;
	r.sTsPlc := '2026-09-08 10:11:12.345';
	r.stEstoque.nA := 4; r.stEstoque.nB := 5; r.stEstoque.nC := 6;
	fb.Build(r, s);
	AssertEquals_STRING(
	  Expected := 'INSERT INTO estoque_hist (ts_plc,estoque_a,estoque_b,estoque_c,origem) VALUES (''2026-09-08 10:11:12.345'',4,5,6,''mudanca'');',
	  Actual := s, Message := 'SQL estoque mudanca');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Build_EstoquePeriodico_OrigemPeriodico
VAR fb : FB_DfiSqlBuilder; r : ST_DfiRow; s : STRING(511); BEGIN
	TEST('Build_EstoquePeriodico');
	r.eKind := E_DfiRowKind.ESTOQUE_PERIODICO;
	r.sTsPlc := '2026-09-08 10:12:12.000';
	r.stEstoque.nA := 0; r.stEstoque.nB := 1; r.stEstoque.nC := 2;
	fb.Build(r, s);
	AssertEquals_STRING(
	  Expected := 'INSERT INTO estoque_hist (ts_plc,estoque_a,estoque_b,estoque_c,origem) VALUES (''2026-09-08 10:12:12.000'',0,1,2,''periodico'');',
	  Actual := s, Message := 'SQL estoque periodico');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Build_Evento_ComPecaEDetalhe
VAR fb : FB_DfiSqlBuilder; r : ST_DfiRow; s : STRING(511); BEGIN
	TEST('Build_Evento_ComPecaEDetalhe');
	r.eKind := E_DfiRowKind.EVENTO;
	r.sTsPlc := '2026-09-08 10:13:00.000';
	r.stEvento.sEvento := 'erro'; r.stEvento.sPeca := 'B'; r.stEvento.sDetalhe := 'timeout';
	r.stEvento.sPayloadRaw := '{type:evento,evento:erro}';
	fb.Build(r, s);
	AssertEquals_STRING(
	  Expected := 'INSERT INTO eventos_hist (ts_plc,evento,peca,detalhe,payload_raw) VALUES (''2026-09-08 10:13:00.000'',''erro'',''B'',''timeout'',''{type:evento,evento:erro}'');',
	  Actual := s, Message := 'SQL evento completo');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_Build_Evento_SemPeca_SemDetalhe_UsaNULL
VAR fb : FB_DfiSqlBuilder; r : ST_DfiRow; s : STRING(511); BEGIN
	TEST('Build_Evento_SemPeca_UsaNULL');
	r.eKind := E_DfiRowKind.EVENTO;
	r.sTsPlc := '2026-09-08 10:14:00.000';
	r.stEvento.sEvento := 'inicializacao'; r.stEvento.sPeca := ''; r.stEvento.sDetalhe := '';
	r.stEvento.sPayloadRaw := '';
	fb.Build(r, s);
	AssertEquals_STRING(
	  Expected := 'INSERT INTO eventos_hist (ts_plc,evento,peca,detalhe,payload_raw) VALUES (''2026-09-08 10:14:00.000'',''inicializacao'',NULL,NULL,'''');',
	  Actual := s, Message := 'peca/detalhe NULL, payload_raw string vazia');
	TEST_FINISHED();
END_METHOD
```

- [ ] **Step 2: ⛳ CHECKPOINT (human) — expect FAIL.**

- [ ] **Step 3: Write `FB_DfiSqlBuilder.TcPOU`**

Declaration: `fbFmt : FB_FormatString;` + locals `sPeca, sDet : STRING(80);`.

`Build` implementation:
- `CASE stRow.eKind OF`
  - `ESTOQUE_MUDANCA, ESTOQUE_PERIODICO:`
    - `sOrigem := SEL(stRow.eKind = E_DfiRowKind.ESTOQUE_MUDANCA, 'periodico', 'mudanca');`
    - `fbFmt(sFormat := 'INSERT INTO estoque_hist (ts_plc,estoque_a,estoque_b,estoque_c,origem) VALUES (''%s'',%d,%d,%d,''%s'');',`
      `arg1 := F_String(stRow.sTsPlc), arg2 := F_INT(stRow.stEstoque.nA), arg3 := F_INT(stRow.stEstoque.nB), arg4 := F_INT(stRow.stEstoque.nC), arg5 := F_String(sOrigem), sOut => sCmd);`
  - `EVENTO:`
    - `sPeca := SEL(stRow.stEvento.sPeca = '', CONCAT('''', CONCAT(stRow.stEvento.sPeca, '''')), 'NULL');`
    - `sDet  := SEL(stRow.stEvento.sDetalhe = '', CONCAT('''', CONCAT(stRow.stEvento.sDetalhe, '''')), 'NULL');`
    - `fbFmt(sFormat := 'INSERT INTO eventos_hist (ts_plc,evento,peca,detalhe,payload_raw) VALUES (''%s'',''%s'',%s,%s,''%s'');',`
      `arg1 := F_String(stRow.sTsPlc), arg2 := F_String(stRow.stEvento.sEvento), arg3 := F_String(sPeca), arg4 := F_String(sDet), arg5 := F_String(stRow.stEvento.sPayloadRaw), sOut => sCmd);`
- `Build := NOT fbFmt.bError;`

> `''` inside a ST string literal is one escaped single quote. Verify the exact `FB_FormatString` escaping for `%` and quotes against the installed `Tc2_Utilities` — adjust the format literal so the **expected strings in Step 1 come out byte-for-byte**. The tests are the contract; make the implementation match them.

- [ ] **Step 4: ⛳ CHECKPOINT (human) — expect PASS** (4 tests). If quoting differs, fix the format string (not the tests) unless the test's expected SQL is itself invalid.

- [ ] **Step 5: Commit** `feat: FB_DfiSqlBuilder (ST_DfiRow -> INSERT) with tests`

---

## Task 10: Time helper `F_DfiNowString`

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/F_DfiNowString.TcPOU` (FUNCTION)
- Create: `TwinCAT Project/PLC/POUs/test/F_DfiNowString_Tests.TcPOU`
- Modify: `FB_DfiSampler.TcPOU` (remove the stub added in Task 6), `PRG_DfiTests.TcPOU`, `PLC.plcproj`

**Interfaces:**
- Consumes: `Tc2_System.FB_LocalSystemTime` (or `GETSYSTEMTIME` + `FILETIME`), `Tc2_Utilities` time-format helpers.
- Produces: `FUNCTION F_DfiNowString : STRING(23)` — no inputs — returns local wall-clock now as `'YYYY-MM-DD HH:MM:SS.mmm'`.

- [ ] **Step 1: Replace the Task 6 stub** — delete the temporary `F_DfiNowString` stub FUNCTION created in Task 6 Step 3 note.

- [ ] **Step 2: Write suite `F_DfiNowString_Tests.TcPOU`** — format-shape assertions (not exact time):

```pascal
METHOD PRIVATE Test_Formato_23Chars_ComSeparadores
VAR s : STRING(23); BEGIN
	TEST('Formato_23Chars');
	s := F_DfiNowString();
	AssertEquals_INT(23, LEN(s), 'comprimento 23');
	AssertEquals_STRING('-', MID(s, 1, 5), 'traco em pos 5');
	AssertEquals_STRING('-', MID(s, 1, 8), 'traco em pos 8');
	AssertEquals_STRING(' ', MID(s, 1, 11), 'espaco em pos 11');
	AssertEquals_STRING(':', MID(s, 1, 14), 'dois-pontos pos 14');
	AssertEquals_STRING('.', MID(s, 1, 20), 'ponto pos 20');
	TEST_FINISHED();
END_METHOD
```

- [ ] **Step 3: ⛳ CHECKPOINT (human) — expect FAIL.**

- [ ] **Step 4: Implement `F_DfiNowString`** using `FB_LocalSystemTime` (`bEnable := TRUE`) → `TIMESTRUCT` (`wYear,wMonth,wDay,wHour,wMinute,wSecond,wMilliseconds`); build the string with `FB_FormatString` or zero-padded `CONCAT`s. Zero-pad each field.

- [ ] **Step 5: ⛳ CHECKPOINT (human) — expect PASS.** Also re-run the full `PRG_DfiTests` suite: all prior suites still green.

- [ ] **Step 6: Commit** `feat: F_DfiNowString timestamp helper; drop sampler stub`

---

## Task 11: TwinCAT Connectivity Project + `DfiDb` connection

**Files:**
- Create: `TwinCAT Connectivity Project/TwinCAT Connectivity Project.tcconnproj`
- Create: `TwinCAT Connectivity Project/TcDatabaseServer/TcDatabaseServer.tcdbsrv`
- Create: `TwinCAT Connectivity Project/TcDatabaseServer/DfiDb/DfiDb.tcdbsrvdb`
- Reference: `Banco-de-Dados/DatabaseServer1/TwinCAT Connectivity Project1/**` (copy + adapt)
- Modify: `TwinCAT Project/TwinCAT Project.sln` (add the connectivity project to the solution)

**Interfaces:**
- Produces: a TwinCAT Database Server DB definition named `DfiDb`, **DB-ID = 1**, provider MySQL/MariaDB, host `127.0.0.1`, port `3306`, database `dfi_historian`, user/password left as config/blank (filled at commissioning). `FB_DfiDbWriter` (Task 12) calls `Connect(hDBID := GVL_Dfi.gCfg.nDbId)` which defaults to 1.

- [ ] **Step 1: Copy `DatabaseServer1`'s connectivity project** to `CX9240_DataFlowInventory/TwinCAT Connectivity Project/`, rename files/name string `TwinCAT Connectivity Project1` → `TwinCAT Connectivity Project`, `DB1` → `DfiDb`, regenerate all GUIDs.

- [ ] **Step 2: Edit `DfiDb.tcdbsrvdb`** — set: `DBType` = `MySQL` (the TF6420 provider id for MySQL/MariaDB — confirm exact enum against the installed configurator), `Server`/`Host` = `127.0.0.1`, `Port` = `3306`, `Database` = `dfi_historian`, `DBID` = `1`. Leave `User`/`Password` blank (the runtime config on the box holds them, or set them here at commissioning and keep this file out of a public push — it lives in a private repo, acceptable, but prefer blank + set on target).

- [ ] **Step 3: Add the connectivity project to the `.sln`** — add the `Project(...) = "TwinCAT Connectivity Project", "TwinCAT Connectivity Project\TwinCAT Connectivity Project.tcconnproj", "{NEW-GUID}"` block + `EndProject`, mirroring how `DatabaseServer1`'s `.sln` lists its connectivity project.

- [ ] **Step 4: ⛳ CHECKPOINT (human) — configurator + Check**

Open the solution in XAE. Under *TwinCAT → Database Server*, set the project's **Target NetId** to the CX9240. Activate config. In the DB config screen press **Check** → expect green (connection to `127.0.0.1:3306/dfi_historian` OK). Requires: MariaDB running on the target with `schema.sql` applied, TF6420 license active, `tf6420-database-server` apt package installed.

- [ ] **Step 5: Commit** `feat: TwinCAT Database Server connectivity project (DfiDb -> local MariaDB)`

---

## Task 12: `FB_DfiDbWriter` (TF6420 state machine)

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiDbWriter.TcPOU`
- Create: `TwinCAT Project/PLC/POUs/test/FB_DfiDbWriter_Tests.TcPOU` (logic-only tests: state transitions with a faked command result)
- Modify: `PRG_DfiTests.TcPOU`, `PLC.plcproj`

**Interfaces:**
- Consumes: `FB_DfiRowBuffer`, `FB_DfiSqlBuilder`, `ST_DfiRow`, `E_DfiRowKind`, `E_DfiWriterState`, `ST_EstoqueSnapshot`, `ST_DfiConfig`, `Tc3_Database.FB_SQLDatabaseEvt`, `Tc3_Database.FB_SQLCommandEvt`, `Tc3_EventLogger.I_TcMessage`.
- Produces: `FB_DfiDbWriter` with
  `VAR_INPUT stConfig : ST_DfiConfig; END_VAR`
  `VAR_IN_OUT fbBuffer : FB_DfiRowBuffer; END_VAR`
  `VAR_OUTPUT eState : E_DfiWriterState; bDbConnected : BOOL; nRowsWritten : ULINT; nErrors : ULINT; sLastError : STRING(255); stUltimoGravado : ST_EstoqueSnapshot; bUltimoGravadoValido : BOOL; END_VAR`
  Called cyclically. Peek→Execute→Pop: never `Pop` unless the INSERT returned no error. One `Execute` kick-off per cycle.

- [ ] **Step 1: Decide the test seam.** `FB_SQLCommandEvt` can't run without a DB. Extract the SQL-string decision into `FB_DfiSqlBuilder` (done, Task 9) and unit-test **only the state machine's row bookkeeping** here by making the "execute" a protected `METHOD DoExecute : INT` (returns `0 busy`, `1 ok`, `2 error`) that the test subclass overrides. Declare `FB_DfiDbWriter` with `METHOD PROTECTED DoExecute : INT` wrapping the real `SQLCommandEvt.Execute(...)`/`bError` polling. Test suite defines `FB_DfiDbWriter_Fake EXTENDS FB_DfiDbWriter` overriding `DoExecute` with a scripted sequence.

- [ ] **Step 2: Write failing suite `FB_DfiDbWriter_Tests.TcPOU`**

```pascal
METHOD PRIVATE Test_Sucesso_PopEContagem
VAR
	fbBuf : FB_DfiRowBuffer := (nCapacity := 8);
	sut   : FB_DfiDbWriter_Fake;   // DoExecute sempre retorna 1 (ok) apos 1 ciclo "busy"
	cfg   : ST_DfiConfig;
	r     : ST_DfiRow;
	i     : INT;
BEGIN
	TEST('Sucesso_PopEContagem');
	sut.SetScript(SCRIPT_OK);      // helper do fake
	r.eKind := E_DfiRowKind.ESTOQUE_MUDANCA; r.stEstoque.nA := 9;
	fbBuf.Push(r);
	FOR i := 1 TO 20 DO sut(stConfig := cfg, fbBuffer := fbBuf); END_FOR
	AssertEquals_UDINT(0, fbBuf.nCount, 'linha removida apos sucesso');
	AssertEquals_ULINT(1, sut.nRowsWritten, 'nRowsWritten=1');
	AssertTrue(sut.bUltimoGravadoValido, 'dedupe baseline valido');
	AssertEquals_INT(9, sut.stUltimoGravado.nA, 'dedupe baseline = ultima linha de estoque');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_ErroExecute_NaoPop_BackoffCresce
VAR
	fbBuf : FB_DfiRowBuffer := (nCapacity := 8);
	sut   : FB_DfiDbWriter_Fake;
	cfg   : ST_DfiConfig;
	r     : ST_DfiRow;
	i     : INT;
BEGIN
	TEST('ErroExecute_NaoPop');
	sut.SetScript(SCRIPT_EXEC_ERROR);   // DoExecute retorna 2 (erro)
	fbBuf.Push(r);
	FOR i := 1 TO 30 DO sut(stConfig := cfg, fbBuffer := fbBuf); END_FOR
	AssertEquals_UDINT(1, fbBuf.nCount, 'linha PRESERVADA apos erro');
	AssertTrue(sut.nErrors >= 1, 'nErrors incrementa');
	AssertTrue(sut.eState = E_DfiWriterState.ERROR OR sut.eState = E_DfiWriterState.IDLE, 'em ERROR/backoff ou voltando');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_DbLost_DuranteExecute_VoltaIdle_SemPerder
VAR
	fbBuf : FB_DfiRowBuffer := (nCapacity := 8);
	sut   : FB_DfiDbWriter_Fake;
	cfg   : ST_DfiConfig;
	r     : ST_DfiRow;
	i     : INT;
BEGIN
	TEST('DbLost_SemPerder');
	sut.SetScript(SCRIPT_DB_LOST);
	fbBuf.Push(r);
	FOR i := 1 TO 20 DO sut(stConfig := cfg, fbBuffer := fbBuf); END_FOR
	AssertEquals_UDINT(1, fbBuf.nCount, 'linha preservada em DB_LOST');
	TEST_FINISHED();
END_METHOD
```

```pascal
METHOD PRIVATE Test_PeriodicoTambemAtualizaBaseline
VAR
	fbBuf : FB_DfiRowBuffer := (nCapacity := 8);
	sut   : FB_DfiDbWriter_Fake;
	cfg   : ST_DfiConfig; r : ST_DfiRow; i : INT;
BEGIN
	TEST('PeriodicoAtualizaBaseline');
	sut.SetScript(SCRIPT_OK);
	r.eKind := E_DfiRowKind.ESTOQUE_PERIODICO; r.stEstoque.nB := 2;
	fbBuf.Push(r);
	FOR i := 1 TO 20 DO sut(stConfig := cfg, fbBuffer := fbBuf); END_FOR
	AssertTrue(sut.bUltimoGravadoValido, 'baseline valido apos periodico');
	AssertEquals_INT(2, sut.stUltimoGravado.nB, 'baseline B=2');
	TEST_FINISHED();
END_METHOD
```

- [ ] **Step 3: ⛳ CHECKPOINT (human) — expect FAIL.**

- [ ] **Step 4: Write `FB_DfiDbWriter.TcPOU`** implementing spec §4.4 exactly:

Declaration:
```pascal
FUNCTION_BLOCK FB_DfiDbWriter
VAR_INPUT
	stConfig : ST_DfiConfig;
END_VAR
VAR_IN_OUT
	fbBuffer : FB_DfiRowBuffer;
END_VAR
VAR_OUTPUT
	eState               : E_DfiWriterState;
	bDbConnected         : BOOL;
	nRowsWritten         : ULINT;
	nErrors              : ULINT;
	sLastError           : STRING(255);
	stUltimoGravado      : ST_EstoqueSnapshot;
	bUltimoGravadoValido : BOOL;
END_VAR
VAR
	fbDb    : Tc3_Database.FB_SQLDatabaseEvt;
	fbCmd   : Tc3_Database.FB_SQLCommandEvt;
	fbBuild : FB_DfiSqlBuilder;
	fbBackoff : TON;
	tBackoff  : TIME := T#2S;
	sCmd    : STRING(511);
	stRow   : ST_DfiRow;
	stEvt   : Tc3_EventLogger.I_TcMessage;
	sClass  : STRING(255);
	bCmdCreated : BOOL;
END_VAR
```

Body — `CASE eState OF` per the spec §4.4 table. Key rules:
- `IDLE`: `IF fbBuffer.nCount > 0 THEN IF bDbConnected THEN eState := BUILD; ELSE eState := CONNECT; END_IF END_IF`
- `CONNECT`: `IF fbDb.Connect(hDBID := stConfig.nDbId) THEN IF fbDb.bError THEN stEvt := fbDb.ipTcResult; eState := ERROR; ELSE IF fbDb.CreateCmd(ADR(fbCmd)) AND NOT fbDb.bError THEN bDbConnected := TRUE; eState := BUILD; END_IF END_IF END_IF`
- `BUILD`: `IF fbBuffer.Peek(stRow) THEN fbBuild.Build(stRow, sCmd); eState := EXECUTE; ELSE eState := IDLE; END_IF`
- `EXECUTE`: call `DoExecute()` → `0` stay; `1` → `eState := COMMIT`; `2` → `stEvt := fbCmd.ipTcResult; eState := ERROR`. Also `IF NOT bDbConnected THEN eState := DB_LOST; END_IF` guard.
- `COMMIT`: `fbBuffer.Pop(); nRowsWritten := nRowsWritten + 1;`
  `IF stRow.eKind = E_DfiRowKind.ESTOQUE_MUDANCA OR stRow.eKind = E_DfiRowKind.ESTOQUE_PERIODICO THEN stUltimoGravado := stRow.stEstoque; bUltimoGravadoValido := TRUE; END_IF`
  `tBackoff := T#2S; IF fbBuffer.nCount = 0 THEN eState := IDLE; ELSE eState := BUILD; END_IF`
- `ERROR`: extract text once:
  `IF stEvt <> 0 THEN stEvt.RequestEventText(1033, sLastError, SIZEOF(sLastError)); END_IF`
  `nErrors := nErrors + 1; fbBackoff(IN := TRUE, PT := tBackoff);`
  `IF fbBackoff.Q THEN fbBackoff(IN := FALSE); tBackoff := MIN_TIME(tBackoff + tBackoff, T#30S); eState := IDLE; END_IF`
  (implement `MIN_TIME` as `SEL(a > b, a, b)` on `TIME` or convert to `TIME_TO_DINT` ms.)
- `DB_LOST`: `bDbConnected := FALSE; eState := IDLE;` (buffer keeps rows.)

`METHOD PROTECTED DoExecute : INT`:
```pascal
// returns 0=busy, 1=ok, 2=error
IF fbCmd.Execute(pSQLCmd := ADR(sCmd), cbSQLCmd := SIZEOF(sCmd)) THEN
	IF fbCmd.bError THEN DoExecute := 2; ELSE DoExecute := 1; END_IF
ELSE
	DoExecute := 0;
END_IF
```

`FB_DfiDbWriter_Fake` (in the test file) `EXTENDS FB_DfiDbWriter`, adds `SetScript(n : INT)` and overrides `DoExecute` to return scripted values (`SCRIPT_OK` → `0` for 1 cycle then `1`; `SCRIPT_EXEC_ERROR` → `2`; `SCRIPT_DB_LOST` → sets `bDbConnected := FALSE` then returns `0`).

- [ ] **Step 5: ⛳ CHECKPOINT (human) — expect PASS** (4 tests). Full `PRG_DfiTests` still green.

- [ ] **Step 6: Commit** `feat: FB_DfiDbWriter TF6420 state machine with logic tests`

---

## Task 13: `FB_DfiMqttSubscriber` (TF6701)

**Files:**
- Create: `TwinCAT Project/PLC/POUs/fb/FB_DfiMqttSubscriber.TcPOU`
- Modify: `PLC.plcproj`

**Interfaces:**
- Consumes: `ST_DfiConfig`, `Tc3_IotBase.FB_IotMqttClient` (+ message-queue API of the installed lib version).
- Produces: `FB_DfiMqttSubscriber` with
  `VAR_INPUT stConfig : ST_DfiConfig; bEnable : BOOL; END_VAR`
  `VAR_OUTPUT bConnected : BOOL; bNewMessage : BOOL; sTopic : STRING(255); sPayload : STRING(510); nReconnectCount : UDINT; END_VAR`
  `bNewMessage` pulses TRUE for exactly one cycle per received message; `sTopic`/`sPayload` valid that cycle.

- [ ] **Step 1: Write `FB_DfiMqttSubscriber.TcPOU`** (no unit test — needs a broker; validated in Task 15 bench)

Declaration:
```pascal
FUNCTION_BLOCK FB_DfiMqttSubscriber
VAR_INPUT
	stConfig : ST_DfiConfig;
	bEnable  : BOOL;
END_VAR
VAR_OUTPUT
	bConnected      : BOOL;
	bNewMessage     : BOOL;
	sTopic          : STRING(255);
	sPayload        : STRING(510);
	nReconnectCount : UDINT;
END_VAR
VAR
	fbMqtt   : Tc3_IotBase.FB_IotMqttClient;
	fbMsg    : Tc3_IotBase.FB_IotMqttMessage;   // confirm type name in installed lib
	bParamsSet : BOOL;
	bWasConnected : BOOL;
	bSubEstoque, bSubEventos : BOOL;
END_VAR
```

Body:
1. `bNewMessage := FALSE;`
2. `IF NOT bEnable THEN fbMqtt.Execute(FALSE); bConnected := FALSE; RETURN; END_IF`
3. One-time param set when `NOT bParamsSet`:
   `fbMqtt.sHostName := stConfig.sMqttHost;`
   `fbMqtt.nHostPort := stConfig.nMqttPort;`
   `fbMqtt.sClientId := 'dataflow-cx9240-historian';`
   `IF stConfig.sMqttUser <> '' THEN fbMqtt.stMQTT.sUserName := stConfig.sMqttUser; fbMqtt.stMQTT.sUserPassword := stConfig.sMqttPass; END_IF` *(confirm member path `stMQTT.sUserName` in the installed lib — may be `sUsername`)*
   `IF stConfig.bUseTls THEN fbMqtt.stTLS.sCA := stConfig.sCaCertPath; END_IF` *(confirm `stTLS.sCA`)*
   `bParamsSet := TRUE;`
4. `fbMqtt.Execute(bConnect := TRUE);`
5. `bConnected := fbMqtt.bConnected;`
6. Reconnect count: `IF bWasConnected AND NOT bConnected THEN nReconnectCount := nReconnectCount + 1; bSubEstoque := FALSE; bSubEventos := FALSE; END_IF` `bWasConnected := bConnected;`
7. On connected, ensure subscriptions once:
   `IF bConnected AND NOT bSubEstoque THEN bSubEstoque := fbMqtt.Subscribe(sTopic := stConfig.sTopicEstoque, eQoS := TcIotMqttQos.AtLeastOnceDelivery); END_IF` (same for `bSubEventos` / `sTopicEventos`).
8. Drain **one** message:
   `IF fbMqtt.ipMessageQueue.nQueuedMessages > 0 THEN IF fbMqtt.ipMessageQueue.Dequeue(fbMsg) THEN fbMsg.GetTopic(sTopic, SIZEOF(sTopic)); fbMsg.GetPayload(ADR(sPayload), SIZEOF(sPayload)-1, bSetNullTermination := TRUE); bNewMessage := TRUE; END_IF END_IF`
   *(exact queue/message API — `ipMessageQueue`, `Dequeue`, `GetTopic`, `GetPayload` — must be confirmed against the installed `Tc3_IotBase`; the shape above matches recent versions. If the lib only offers the callback property, implement `FB_IotMqttMessageCallback` instead and push into a small internal array read out one-per-cycle.)*

- [ ] **Step 2: ⛳ CHECKPOINT (human) — build only.** Expect 0 errors. Runtime behaviour validated in Task 15.

- [ ] **Step 3: Commit** `feat: FB_DfiMqttSubscriber (TF6701 subscribe + dequeue)`

---

## Task 14: `MAIN` orchestration + diagnostics

**Files:**
- Modify: `TwinCAT Project/PLC/POUs/MAIN.TcPOU`
- Modify: `TwinCAT Project/PLC/GVLs/GVL_Dfi.TcGVL` (add FB instances)

**Interfaces:**
- Consumes: every FB above + `GVL_Dfi.gCfg` / `gDiag`.
- Produces: the running application. No new public interface.

- [ ] **Step 1: Add global FB instances to `GVL_Dfi`** (so ADS/HMI can inspect them):

```pascal
VAR_GLOBAL
	gCfg  : ST_DfiConfig;
	gDiag : ST_DfiDiag;
	// pipeline
	fbLoader  : FB_DfiConfigLoader;
	fbSub     : FB_DfiMqttSubscriber;
	fbParser  : FB_DfiPayloadParser;
	fbBuffer  : FB_DfiRowBuffer;
	fbSampler : FB_DfiSampler;
	fbWriter  : FB_DfiDbWriter;
END_VAR
```

- [ ] **Step 2: Write `MAIN`** per spec §4.6:

```pascal
PROGRAM MAIN
VAR
	bBoot          : BOOL := TRUE;
	stUltimoEstoque : ST_EstoqueSnapshot;
	bEstoqueValido  : BOOL;
	bDiff           : BOOL;
	row             : ST_DfiRow;
END_VAR
// ---------------------------------------------------------------
// 0. Config (uma vez no arranque; retenta se falhar)
IF bBoot THEN
	GVL_Dfi.fbLoader(bExecute := TRUE, sPath := '/etc/dfi/historian.conf');
	IF GVL_Dfi.fbLoader.bDone THEN
		bBoot := FALSE;
		IF NOT GVL_Dfi.fbLoader.bError AND GVL_Dfi.fbLoader.stCfg.bValid THEN
			GVL_Dfi.gCfg := GVL_Dfi.fbLoader.stCfg;
		END_IF
	END_IF
END_IF
GVL_Dfi.gDiag.bConfigOk := GVL_Dfi.gCfg.bValid;
IF NOT GVL_Dfi.gCfg.bValid THEN RETURN; END_IF   // sem config valida, nao conecta em nada

GVL_Dfi.fbBuffer(nCapacity := GVL_Dfi.gCfg.nBufferSize);

// 1. MQTT
GVL_Dfi.fbSub(stConfig := GVL_Dfi.gCfg, bEnable := TRUE);

// 2. Parse + roteamento
IF GVL_Dfi.fbSub.bNewMessage THEN
	GVL_Dfi.fbParser(bExecute := TRUE, sTopic := GVL_Dfi.fbSub.sTopic,
	                 sPayload := GVL_Dfi.fbSub.sPayload, stConfig := GVL_Dfi.gCfg);
	IF GVL_Dfi.fbParser.bOk THEN
		CASE GVL_Dfi.fbParser.eKind OF
			E_DfiRowKind.ESTOQUE_MUDANCA:
				stUltimoEstoque := GVL_Dfi.fbParser.stEstoque;
				bEstoqueValido  := TRUE;
				bDiff := (NOT GVL_Dfi.fbWriter.bUltimoGravadoValido)
				      OR (GVL_Dfi.fbParser.stEstoque.nA <> GVL_Dfi.fbWriter.stUltimoGravado.nA)
				      OR (GVL_Dfi.fbParser.stEstoque.nB <> GVL_Dfi.fbWriter.stUltimoGravado.nB)
				      OR (GVL_Dfi.fbParser.stEstoque.nC <> GVL_Dfi.fbWriter.stUltimoGravado.nC);
				IF bDiff THEN
					row.eKind := E_DfiRowKind.ESTOQUE_MUDANCA;
					row.sTsPlc := F_DfiNowString();
					row.stEstoque := GVL_Dfi.fbParser.stEstoque;
					GVL_Dfi.fbBuffer.Push(row);
				END_IF
			E_DfiRowKind.EVENTO:
				row.eKind := E_DfiRowKind.EVENTO;
				row.sTsPlc := F_DfiNowString();
				row.stEvento := GVL_Dfi.fbParser.stEvento;
				GVL_Dfi.fbBuffer.Push(row);
		END_CASE
	ELSE
		GVL_Dfi.gDiag.nParseErrors := GVL_Dfi.gDiag.nParseErrors + 1;
		GVL_Dfi.gDiag.sUltimoParseError := GVL_Dfi.fbParser.sParseError;
	END_IF
	GVL_Dfi.fbParser(bExecute := FALSE);
END_IF

// 3. Amostra periodica
GVL_Dfi.fbSampler(stUltimoEstoque := stUltimoEstoque, bValido := bEstoqueValido,
                  tPeriodo := GVL_Dfi.gCfg.tSamplePeriod, fbBuffer := GVL_Dfi.fbBuffer);

// 4. Dreno para o banco
GVL_Dfi.fbWriter(stConfig := GVL_Dfi.gCfg, fbBuffer := GVL_Dfi.fbBuffer);

// 5. Diagnostico
GVL_Dfi.gDiag.bMqttConnected   := GVL_Dfi.fbSub.bConnected;
GVL_Dfi.gDiag.nReconnectCount  := GVL_Dfi.fbSub.nReconnectCount;
GVL_Dfi.gDiag.bDbConnected     := GVL_Dfi.fbWriter.bDbConnected;
GVL_Dfi.gDiag.eWriterState     := GVL_Dfi.fbWriter.eState;
GVL_Dfi.gDiag.nRowsWritten     := GVL_Dfi.fbWriter.nRowsWritten;
GVL_Dfi.gDiag.nDbErrors        := GVL_Dfi.fbWriter.nErrors;
GVL_Dfi.gDiag.sUltimoDbError   := GVL_Dfi.fbWriter.sLastError;
GVL_Dfi.gDiag.nBufferCount     := GVL_Dfi.fbBuffer.nCount;
GVL_Dfi.gDiag.nBufferHighWater := GVL_Dfi.fbBuffer.nHighWater;
GVL_Dfi.gDiag.nBufferDropped   := GVL_Dfi.fbBuffer.nDropped;
```

- [ ] **Step 3: ⛳ CHECKPOINT (human) — build.** 0 errors. Boot project: exclude `POUs/test/` from the boot build for the production configuration (see Task 5 Step 2).

- [ ] **Step 4: Commit** `feat: MAIN orchestration + diagnostics for CX9240 historian`

---

## Task 15: Commissioning docs

**Files:**
- Create: `docs/comissionamento-rt-linux.md`
- Create: `docs/necessidades-integracao.md`
- Create: `docs/roteiro-testes-bancada.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: `docs/necessidades-integracao.md`** — copy spec §8 verbatim (the 14-row table + intro sentence), add a one-line header linking back to the spec.

- [ ] **Step 2: `docs/roteiro-testes-bancada.md`** — copy spec §7.2 (8 scenarios) as a numbered checklist with a results column (`[ ] pass / fail / notes`).

- [ ] **Step 3: `docs/comissionamento-rt-linux.md`** — write the deploy walkthrough, sections in order:
  1. **Pré-requisitos** — CX9240 com RT Linux (ver *Primeiros passos no Beckhoff RT Linux*), PC de engenharia com TwinCAT XAE, conta myBeckhoff.
  2. **Pacotes (apt)** — `bhf.conf` auth; `sudo apt update`; `sudo apt install tc31-xar-um`; `sudo apt install tf6701-iot-communication tf6420-database-server mariadb-server` *(confirmar nomes exatos no Package Server para arm64/bookworm)*; `sudo systemctl enable --now mariadb`.
  3. **Banco** — `sudo mysql_secure_installation`; criar usuário app: `CREATE USER 'dfi'@'localhost' IDENTIFIED BY '<senha>'; GRANT INSERT,SELECT ON dfi_historian.* TO 'dfi'@'localhost';`; `mysql -u root -p < schema.sql`.
  4. **NTP** — `sudo apt install chrony` (ou `systemd-timesyncd`); conferir `timedatectl`; definir timezone (`sudo timedatectl set-timezone America/Sao_Paulo`).
  5. **Firewall (nftables)** — arquivo `/etc/nftables.conf.d/60-ads.conf` liberando TCP 48898 na interface de engenharia (exemplo do material RT Linux); `sudo systemctl reload nftables`. 3306 permanece em loopback (sem regra). Saída 8883 para HiveMQ (só se `mqtt_use_tls=1`).
  6. **Config** — `sudo mkdir -p /etc/dfi`; copiar `historian.conf.example` → `/etc/dfi/historian.conf`; `sudo chmod 600 /etc/dfi/historian.conf`; preencher host do broker, credenciais, `db_id=1`.
  7. **Licenças** — em XAE: `System → License → Manage Licenses` → adicionar TF6701, TF6020, TF6420, TC1200 → `Order Information → 7 Days Trial` (ou licença definitiva) → `Ctrl+Shift+S`.
  8. **Rota ADS** — criar rota do PC de engenharia para o CX9240 (nome/AmsNetId/IP).
  9. **Database Server** — abrir a solução; `TwinCAT → Database Server`; setar **Target NetId** = CX9240; na conexão `DfiDb` preencher usuário `dfi`/senha; **Check** → verde.
  10. **Deploy do PLC** — setar target = CX9240; **excluir `POUs/test/` do boot project** na configuração de produção; `Activate Configuration`; `Activate Boot Project`; `Login` + `Run`.
  11. **Verificação** — rodar `docs/roteiro-testes-bancada.md`.

- [ ] **Step 4: Commit** `docs: CX9240 historian commissioning, needs report, bench test script`

---

## Task 16: End-to-end bench pass + finalize

**Files:**
- Modify: `docs/roteiro-testes-bancada.md` (fill results), `README.md` (status line)

- [ ] **Step 1: ⛳ CHECKPOINT (human) — execute all 8 scenarios** in `docs/roteiro-testes-bancada.md` against the CX9240 + a Mosquitto broker + the DataFlowInventory simulator or `mosquitto_pub`. Record pass/fail/notes for each.

- [ ] **Step 2: Fix any failures** — loop back to the owning task, add a regression TcUnit test where the failure is logic-level.

- [ ] **Step 3: Update `README.md`** — set a status line: `Status: validado em bancada (CX9240 + Mosquitto local) em <data>` or the honest partial state.

- [ ] **Step 4: Commit** `test: e2e bench validation results for CX9240 historian`

- [ ] **Step 5: Open PR** against `TwinCAT` `main` from `feat/cx9240-mqtt-historian`.

```bash
gh pr create --repo MatheusNespolo/TwinCAT --base main --head feat/cx9240-mqtt-historian \
  --title "CX9240 MQTT historian for Data Flow Inventory (TF6701 + TF6420)" \
  --body "Implements docs/2026-09-08-cx9240-mqtt-historian-design.md — a CX9240/RT Linux node that subscribes to dataflow/estoque + dataflow/eventos and logs to a local MariaDB via TF6420 SQL Expert Mode. Includes TcUnit suites, connectivity project, schema.sql and commissioning docs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task(s) |
|---|---|
| §1 papel / arquitetura | 3, 14 (orchestration), 13 (subscriber-only, never publishes) |
| §1.3 decisões | 1 (wide+periodic schema), 11 (local MariaDB), 5–6 (FIFO), 12 (SQL Expert Mode) |
| §2 contrato de dados MQTT | 8 (parser: topics, payloads, retained handled via dedupe in 14) |
| §2.4 robustez do contrato | 8 (`nParseErrors`), 4 (`ST_DfiDiag`), 14 (diag wiring) |
| §3 estrutura de pastas | 2, 3, 5–14 (files created exactly where §3 lists) |
| §3.1 bibliotecas | 3 (refs) |
| §4.1 `FB_DfiMqttSubscriber` | 13 |
| §4.2 `FB_DfiPayloadParser` + sanitização | 8 |
| §4.3 `FB_DfiRowBuffer` | 5 |
| §4.4 `FB_DfiDbWriter` (state machine, peek→exec→pop, backoff) | 12 |
| §4.5 `FB_DfiSampler` | 6 |
| §4.6 `MAIN` + dedupe vs último gravado | 14 |
| §5 schema + SQL строки | 1, 9 |
| §5.3 sanitização é o anteparo | 8 (`F_DfiSanitizeText`, `F_DfiStripSqlUnsafe`) |
| §6 config + segredos (`/etc/dfi/historian.conf`, fora do VCS) | 2 (`.example`, gitignore), 7 (parser+loader), 15 (deploy) |
| §6.3 TLS RT Linux | 7 (`sCaCertPath`), 13 (`stTLS.sCA`), 15 (nftables/8883) |
| §7.1 testes unitários TcUnit | 5, 6, 7, 8, 9, 10, 12 |
| §7.2 testes de bancada | 15 (script), 16 (execute) |
| §7.3 soak | 16 Step 1 notes (fold into bench pass) — **covered lightly**; acceptable, soak is observational |
| §8 relatório de necessidades | 15 (`necessidades-integracao.md`) |
| §9 regras herdadas | 13 (no publish, clientId), 2 (secrets), covered in Global Constraints |
| §10 notas de implementação | 3 (task priority), Global Constraints (SIZEOF, error idiom), 12 (Connect/CreateCmd once, ipTcResult) |
| §11 trabalho futuro | out of scope by design — not tasked |

No spec requirement is left without a task. §7.3 (soak) is folded into Task 16 as observation rather than a gated test — deliberate, noted.

**2. Placeholder scan:** No "TBD/TODO/implement later". Library-member names flagged "confirm against installed lib" are genuine external unknowns (TF6701 version drift), each with a concrete fallback (callback path) — not hand-waving. All test steps contain real assertion code or concrete enumerated cases with inputs + expected `sParseError`. `GENERATE-NEW-GUID` placeholders are instructions to the executor (each `.TcPOU` legitimately needs a unique GUID), not unfilled design gaps.

**3. Type consistency:**
- `ST_EstoqueSnapshot` fields `nA/nB/nC : INT` — used consistently in Tasks 6, 8, 9, 12, 14.
- `ST_EventoDfi` fields `sEvento/sPeca/sDetalhe/sPayloadRaw` — consistent Tasks 8, 9.
- `E_DfiRowKind` members `ESTOQUE_MUDANCA/ESTOQUE_PERIODICO/EVENTO` — consistent everywhere.
- `E_DfiWriterState` members `IDLE/CONNECT/BUILD/EXECUTE/COMMIT/ERROR/DB_LOST` — Task 4 defines, Task 12 uses all.
- `FB_DfiRowBuffer` methods `Push/Peek/Pop` + outputs `nCount/nHighWater/nDropped` — consistent Tasks 5, 6, 12, 14.
- `FB_DfiPayloadParser` I/O (`bExecute/sTopic/sPayload/stConfig` → `bOk/eKind/stEstoque/stEvento/sParseError`) — consistent Tasks 8, 14.
- `FB_DfiSqlBuilder.Build(stRow, sCmd)` — consistent Tasks 9, 12.
- `FB_DfiDbWriter` outputs `stUltimoGravado/bUltimoGravadoValido` consumed by `MAIN` dedupe — consistent Tasks 12, 14 (matches spec §4.6 correction).
- `F_DfiNowString : STRING(23)` — stub in Task 6, real in Task 10, consumed in 6/14.
- Config keys: `historian.conf.example` (Task 2) ↔ `FB_DfiCfgParse` branches (Task 7) ↔ `ST_DfiConfig` fields (Task 4) — names line up (`mqtt_host`→`sMqttHost`, `sample_period_s`→`tSamplePeriod`, etc.).

One fix applied during review: Task 8 originally sanitized `payload_raw` with the strict allowlist (would always blank it for real JSON). Corrected in Task 8 Steps 4–5 to use a lighter `F_DfiStripSqlUnsafe` for raw only; `evento`/`detalhe` keep the strict allowlist gate.

---

## Execution Handoff

**Plan complete and saved to `Banco-de-Dados/CX9240_DataFlowInventory/docs/2026-09-08-cx9240-mqtt-historian-plan.md`.**

Two caveats specific to this plan:
- **Build/test verification is human-in-the-loop.** Every ⛳ CHECKPOINT needs someone with TwinCAT XAE + a TC3 runtime to build / run TcUnit and report back. A coding subagent can only produce the source artifacts.
- **Several TF6701/TF6420 member names are pinned only at implementation time** against the libraries installed on the CX9240 — the plan flags each spot and gives a fallback.

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks. Works well for Tasks 1–2, 4–10, 12 (pure artifact generation). Tasks 3, 11, 13–16 need your XAE checkpoints inline.
2. **Inline Execution** — I do the tasks in this session with checkpoints for your review.

Which approach?
