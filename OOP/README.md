# OOP

Programação orientada a objetos aplicada a PLC: interfaces, herança, function blocks abstratos.

## Projetos

- **[OOP_Application_Demo_Starter](OOP_Application_Demo_Starter/)** — ponto de partida do tutorial oficial: lógica de esteira/motor direto no `MAIN`, sem abstração.
- **[OOP_Application_Demo_Final](OOP_Application_Demo_Final/)** — mesma aplicação após a refatoração: `FB_MotorContactor`, `FB_ConveyorMachine`, interfaces `I_Pushbutton`/`I_Sensor`. Compare com o `_Starter` para ver o "antes/depois".
- **[PLC-OOP-Basics-main](PLC-OOP-Basics-main/)** — cópia do repositório oficial [Beckhoff PLC-OOP-Basics](https://github.com/Beckhoff-USA-Corporate/PLC-OOP-Basics) (mantido README/LICENSE originais), com 4 tutoriais: Flash Generator (herança/overriding), Light Control (interfaces), Abstract Drive (abstração), Lighting Controller (extensão).
- **[SagatowskiProg](SagatowskiProg/)** — `FB_Rectangle`/`FB_RectangleChild` (herança), interface `I_Shape`, `EventLogger`, diagrama de classes.

## Possíveis assuntos futuros

- Padrões de projeto (Strategy, Observer, Factory) aplicados a automação
- Biblioteca própria de Function Blocks reutilizáveis entre projetos
- Testes unitários (TcUnit) para FBs com interface
