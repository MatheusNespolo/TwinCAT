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
