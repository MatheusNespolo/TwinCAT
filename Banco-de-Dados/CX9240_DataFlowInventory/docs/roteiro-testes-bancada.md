# Roteiro de testes de bancada — CX9240 Historiador MQTT → SQLite

> Banco: **SQLite** (`/var/lib/dfi/historian.db`) — ver `comissionamento-rt-linux.md`. Consultas
> de verificação: `sqlite3 /var/lib/dfi/historian.db "SELECT * FROM estoque_hist ORDER BY id DESC LIMIT 10;"`

Cópia navegável da **§7.2** do design: [`2026-09-08-cx9240-mqtt-historian-design.md`](2026-09-08-cx9240-mqtt-historian-design.md). Em caso de divergência, o design é a fonte de verdade.

Para o comissionamento do CX9240 antes de rodar este roteiro, ver [`comissionamento-rt-linux.md`](comissionamento-rt-linux.md).

---

## Pré-requisitos

- [ ] **CX9240 comissionado** — apt, licenças, NTP, nftables, `historian.conf`, rota ADS, Database Server e deploy do PLC concluídos (ver [`comissionamento-rt-linux.md`](comissionamento-rt-linux.md)).
- [ ] **Broker Mosquitto na bancada** — Mosquitto local na porta `1883` (padrão de bancada), alcançável pelo CX9240 no host/porta de `historian.conf`.
- [ ] **Publicador de teste** — simulador do `DataFlowInventory` **OU** `mosquitto_pub` (pacote `mosquitto-clients`) para injetar payloads nos tópicos.
- [ ] **Banco SQLite** — `/var/lib/dfi/historian.db` criado com o schema aplicado (`sqlite3 /var/lib/dfi/historian.db < docs/schema_sqlite.sql`), tabelas `estoque_hist` e `eventos_hist` presentes (`.tables`), diretório `/var/lib/dfi` gravável pelo runtime.
- [ ] **Licenças TF ativas** — TF6701, TF6020, TF6420, TC1200 (trial de 7 dias ou definitivas) ativadas no target.
- [ ] **Observabilidade** — `GVL_Dfi.gDiag` acessível via ADS/HMI para conferir `nParseErrors`, `nDropped`, `nHighWater`, `nRowsWritten`, `eWriterState`.

---

## Cenários

1. **Estoque — uma mudança gera uma linha `mudanca`**
   `mosquitto_pub -t dataflow/estoque -m '{"type":"estoque","pecaA":4,"pecaB":5,"pecaC":5}'`
   → 1 linha `mudanca` em `estoque_hist`.
   - [ ] resultado: ____
   - notas: ____

2. **Amostragem periódica — sem tráfego, o sampler continua gravando**
   Sem publicar nada por 3 × `tSamplePeriod`
   → 3 linhas `periodico` com o mesmo A/B/C.
   - [ ] resultado: ____
   - notas: ____

3. **Eventos — entrega e erro com campos corretos**
   `dataflow/eventos` com `entrega` (peça A) e `erro`/`timeout` (peça B)
   → 2 linhas em `eventos_hist` com `peca`/`detalhe`/`payload_raw` corretos.
   - [ ] resultado: ____
   - notas: ____

4. **Store-and-forward — banco fora do ar não perde nem embaralha linhas**
   Simular indisponibilidade do arquivo SQLite: `chmod 000 /var/lib/dfi/historian.db` (ou renomear
   o `.db`); publicar 10 mudanças distintas; restaurar (`chmod 664` / renomear de volta).
   → as 10 linhas aparecem **em ordem**; `nDropped = 0`; `nHighWater ≈ 10`; `nDbErrors` subiu
   durante o bloqueio e parou depois.
   *(Com MariaDB o teste seria `systemctl stop/start mariadb` — ver Apêndice A do comissionamento.)*
   - [ ] resultado: ____
   - notas: ____

5. **Broker fora do ar — sem duplicar `mudanca` pelo retained**
   Derrubar o broker 60 s e voltar
   → **nenhuma** linha `mudanca` duplicada pelo retained; série `periodico` sem buraco no intervalo (CX seguiu vivo).
   - [ ] resultado: ____
   - notas: ____

6. **Queda de energia — banco íntegro após reboot sob carga**
   Reboot do CX9240 sob carga
   → banco sem corrupção; no máximo a última transação perdida.
   - [ ] resultado: ____
   - notas: ____

7. **Troca de broker — migração para HiveMQ Cloud (TLS)**
   Trocar `historian.conf` para HiveMQ Cloud (TLS/8883), reiniciar PLC
   → reconecta e volta a gravar.
   - [ ] resultado: ____
   - notas: ____

8. **Robustez do parser — payload malformado e tentativa de injeção**
   Publicar `{"type":"estoque","pecaA":"x"}` e um evento com `detalhe:"'; DROP TABLE eventos_hist;--"`
   → ambas rejeitadas, `nParseErrors += 2`, tabelas intactas.
   - [ ] resultado: ____
   - notas: ____

---

## Carga / soak (§7.3, opcional nesta bancada)

Simulador do `DataFlowInventory` rodando algumas horas contra o CX9240. Observar: cycle time da PlcTask, `nHighWater` do buffer, crescimento das tabelas, I/O de escrita no microSD, uso de CPU do Cortex-A53.

- [ ] resultado: ____
- notas: ____
