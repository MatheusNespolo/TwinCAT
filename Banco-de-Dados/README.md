# Banco-de-Dados

Conectividade com banco de dados via TF6420 (TwinCAT Database Server).

## Projetos

- **[DatabaseServer1](DatabaseServer1/)** — máquinas de estado completas de escrita (`EscreverDB.TcPOU`, INSERT) e leitura (`LerDB.TcPOU`, SELECT) usando `FB_SQLDatabaseEvt`/`FB_SQLCommandEvt`/`FB_SQLResultEvt`, com DUT `ST_VALORES` e conexão `DB1` configurada no projeto de conectividade.

## Possíveis assuntos futuros

- Logging histórico com Grafana/InfluxDB a partir do TF6420
- UPDATE/DELETE parametrizados
- Pool de conexões / tratamento de reconexão
