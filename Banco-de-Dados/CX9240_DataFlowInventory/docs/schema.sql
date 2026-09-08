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
