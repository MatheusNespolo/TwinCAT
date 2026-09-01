# Exercício 02 — Movimentos Básicos (Absoluto, Relativo, Parada)

**Nível:** 1 — Básico

## Cenário

Com o eixo já habilitado (Exercício 01), agora você vai comandar os movimentos mais comuns de um
eixo linear: ir para uma posição absoluta, deslocar-se um valor relativo, e parar de duas formas
diferentes (parada normal e parada de emergência/travada).

## O que fazer

Usando `GVL_Axes.Axis1` (eixo já habilitado):

1. Instancie `MC_MoveAbsolute` para mover o eixo até a posição `50.0` mm com velocidade `50.0` mm/s,
   disparado por uma borda em `xMoverAbsoluto`.
2. Instancie `MC_MoveRelative` para deslocar o eixo `+20.0` mm a partir da posição atual, com
   velocidade `20.0` mm/s, disparado por `xMoverRelativo`.
3. Instancie `MC_Halt` para parar o eixo suavemente (respeitando a rampa de desaceleração),
   disparado por `xParadaSuave`.
4. Instancie `MC_Stop` para parar o eixo e **bloquear** qualquer novo comando de movimento enquanto
   `Execute` estiver `TRUE` (é a "parada travada"), disparado por `xParadaTravada`.
5. Exponha `xEstadoEixo` ← `Axis1.NcToPlc.AxisState` e `xComandoConcluido` ← que deve ser `TRUE`
   quando qualquer um dos blocos de movimento reportar `Done`.

## Elementos da biblioteca Motion exigidos

- `MC_MoveAbsolute` (move para posição absoluta)
- `MC_MoveRelative` (move um deslocamento relativo à posição atual)
- `MC_Halt` (parada suave, permite novos comandos depois)
- `MC_Stop` (parada travada — bloqueia novos movimentos enquanto ativo)
- `Axis.Status.Moving` (indicação de eixo em movimento)

## Critérios de aceite

- Só um comando de movimento deve executar por vez (não dispare `MC_MoveAbsolute` e
  `MC_MoveRelative` simultaneamente — isso gera erro de eixo ocupado).
- `MC_Stop` deve impedir que `MC_MoveAbsolute`/`MC_MoveRelative` movam o eixo enquanto
  `xParadaTravada` estiver `TRUE`. Ao desligar `xParadaTravada`, o eixo volta a aceitar comandos.
- `xEixoEmMovimento` deve acompanhar corretamente o `Status.Moving` do eixo.

## Dica

Compare com os trechos `//Move Relative`, `//Move Absolute`, `//Parar o Eixo1` e
`//Parar o Eixo1 e impedir que se mova...` do `MAIN.TcPOU` do projeto
[`MotionControl`](../../../MotionControl/).
