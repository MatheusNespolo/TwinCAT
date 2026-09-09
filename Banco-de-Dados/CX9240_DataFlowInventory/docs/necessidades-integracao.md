# Necessidades de integração — CX9240 Historiador MQTT → MariaDB

Cópia navegável da **§8** do design: [`2026-09-08-cx9240-mqtt-historian-design.md`](2026-09-08-cx9240-mqtt-historian-design.md). Em caso de divergência, o design é a fonte de verdade.

---

## Relatório — necessidades que a integração pode ocasionar

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
