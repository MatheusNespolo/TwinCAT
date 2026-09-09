-- dfi_historian — schema SQLite para o CX9240 (Beckhoff RT Linux ARM64).
--
-- Usado no lugar do MariaDB: o TwinCAT Database Server (TF6420) no RT Linux
-- ARM64 nao expoe provedor MySQL/MariaDB que conecte de forma estavel; SQLite
-- e suportado localmente, sem servidor, sem usuario/senha.
--
-- O codigo PLC NAO muda: FB_DfiSqlBuilder gera INSERT INTO ... VALUES (...)
-- padrao, valido tambem no SQLite. So mudam este schema e a config do DfiDb
-- (Database Type = SQLite, caminho do arquivo).
--
-- Aplicar uma vez no CX9240 (arquivo em /var/lib/dfi/historian.db):
--     sudo mkdir -p /var/lib/dfi
--     sudo chmod 777 /var/lib/dfi          # ou chown para o usuario do runtime TwinCAT
--     sqlite3 /var/lib/dfi/historian.db < schema_sqlite.sql
-- (idempotente: pode rodar de novo sem erro)

PRAGMA journal_mode = WAL;   -- 1 escritor (o historiador) + leituras concorrentes (browsing/Grafana)

-- Historico de estoque (formato largo): 1 linha por mudanca E por amostra periodica.
CREATE TABLE IF NOT EXISTS estoque_hist (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_plc     TEXT    NOT NULL,                        -- 'YYYY-MM-DD HH:MM:SS.mmm' (F_DfiNowString, hora local)
  ts_db      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')),
  estoque_a  INTEGER NOT NULL,
  estoque_b  INTEGER NOT NULL,
  estoque_c  INTEGER NOT NULL,
  origem     TEXT    NOT NULL CHECK (origem IN ('mudanca', 'periodico'))
);
CREATE INDEX IF NOT EXISTS ix_estoque_ts ON estoque_hist (ts_plc);

-- Eventos de entrega/erro (dataflow/eventos).
CREATE TABLE IF NOT EXISTS eventos_hist (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_plc      TEXT    NOT NULL,
  ts_db       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now', 'localtime')),
  evento      TEXT    NOT NULL,                        -- 'entrega' | 'erro' | 'inicializacao' | ...
  peca        TEXT,                                    -- 'A' | 'B' | 'C' | NULL
  detalhe     TEXT,                                    -- campo "tipo" do payload de erro (ex.: 'timeout') | NULL
  payload_raw TEXT                                     -- JSON original filtrado (auditoria) | NULL
);
CREATE INDEX IF NOT EXISTS ix_eventos_ts ON eventos_hist (ts_plc);
