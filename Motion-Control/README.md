# Motion-Control

Controle de movimento (NC) via blocos `MC_*` do PLCopen.

## Projetos

- **[MotionControl](MotionControl/)** — dois eixos com `MC_Power`, `MC_Reset`, `MC_MoveRelative`, `MC_MoveAbsolute`, `MC_MoveVelocity`, `MC_Halt`, `MC_Stop`, `MC_MoveModulo`.
- **[Exercicios-Motion](Exercicios-Motion/)** — trilha de exercícios práticos por nível (básico →
  intermediário → avançado → simulado), com enunciado em `README.md` e gabarito comentado em
  `.TcPOU`/`.TcDUT` para cada um, preparando para a **PROVA PRÁTICA de certificação de Motion**.

## Possíveis assuntos futuros

- Multi-eixo/interpolação (`MC_MoveLinearAbsolute`, `MC_MoveCircularAbsolute`)
- Cames eletrônicos (`MC_CamTableSelect`)
- Aplicação estilo CNC simples

> Os projetos [`NCFundamentals`](../Inacabados/Motion-Control/NCFundamentals/) e [`ScopeTest`](../Inacabados/Motion-Control/ScopeTest/) também são desse assunto, mas estão em [`Inacabados/`](../Inacabados/) por não terem lógica implementada.
