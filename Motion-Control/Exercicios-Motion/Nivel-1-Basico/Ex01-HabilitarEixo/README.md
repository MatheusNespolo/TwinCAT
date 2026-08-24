# Exercício 01 — Habilitar Eixo e Ler Status

**Nível:** 1 — Básico

## Cenário

Antes de mover qualquer eixo em TwinCAT, ele precisa estar **energizado (powered)** e seu status
precisa ser lido a cada ciclo. Este é o primeiro passo obrigatório de qualquer aplicação de Motion.

## O que fazer

Usando o eixo `GVL_Axes.Axis1` (declarado como `AXIS_REF` na GVL do projeto `MotionControl`):

1. Chame `Axis1.ReadStatus()` a cada ciclo de PLC (isso atualiza a estrutura `Axis1.Status` com os
   bits de habilitado, em movimento, erro, etc. — sem isso, os status ficam desatualizados).
2. Declare uma entrada digital simulada `xHabilitaEixo : BOOL`.
3. Instancie um bloco `MC_Power` e conecte:
   - `Axis := Axis1`
   - `Enable := xHabilitaEixo`
   - `Enable_Positive := xHabilitaEixo`
   - `Enable_Negative := xHabilitaEixo`
   - `Override := 100.0` (100% de velocidade)
4. Exponha duas saídas booleanas para depuração:
   - `xEixoHabilitado` ← `MC_Power.Status`
   - `xEixoComErro` ← `Axis1.Status.Error`

## Elementos da biblioteca Motion exigidos

- `AXIS_REF` (referência de eixo)
- `MC_Power` (habilita/desabilita o eixo, controla direções permitidas via `Enable_Positive`/`Enable_Negative`)
- `Axis.ReadStatus()` / `Axis.Status` (leitura de status do eixo)

## Critérios de aceite

- Ao ligar `xHabilitaEixo`, `xEixoHabilitado` deve ir para `TRUE` somente depois que `MC_Power.Status`
  confirmar (não é instantâneo — há um pequeno atraso de habilitação do drive/simulação).
- Ao desligar `xHabilitaEixo`, o eixo deve desabilitar e `xEixoHabilitado` deve voltar a `FALSE`.
- Se ocorrer algum erro simulado no eixo, `xEixoComErro` deve refletir isso mesmo com o eixo desabilitado.

## Dica

Compare com o trecho `//Habilitar Eixo1` e `//Habilitar Eixo2` do `MAIN.TcPOU` do projeto
[`MotionControl`](../../../MotionControl/) — ele já mostra o padrão básico de uso do `MC_Power`.
