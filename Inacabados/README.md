# Inacabados

Projetos sem lógica de PLC implementada — normalmente esqueletos criados a partir de templates padrão do TwinCAT ("TwinCAT Project1", "Untitled1", "PLC1") e nunca preenchidos, ou soluções (`.sln`/`.tsproj`) sem nenhum sub-projeto anexado. Ficam separados aqui, organizados pelas mesmas categorias do restante do repositório, para não confundir "estudo em andamento" com exemplo funcional.

Cada um é candidato a virar um exemplo completo — veja a sugestão de assunto na respectiva categoria (ex: [`Motion-Control/README.md`](../Motion-Control/README.md)).

## PLC-Fundamentos

- **[GettingStarted](PLC-Fundamentos/GettingStarted/)** — `MAIN` vazio; segundo sub-projeto sem PLC anexado. Esqueleto de "primeiro projeto".

## Motion-Control

- **[NCFundamentals](Motion-Control/NCFundamentals/)** — I/O configurado (EK1200, EL1012, EL2008, EL7031, EL3062, EL4002, EK1110, EK1100, EL2809, EL6900), mas `MAIN` vazio.
- **[ScopeTest](Motion-Control/ScopeTest/)** — eixo habilitado, mas o movimento em si não foi implementado (comentário "Chama o programa de movimento" sem código). Inclui projeto de Scope (`Scope.tcmproj`) para captura de sinais.

## Comunicacao-Rede

- **[OPC_Conectivity_Test](Comunicacao-Rede/OPC_Conectivity_Test/)** — apenas `.sln`/`.tsproj`, sem sub-projeto.
- **[FTP-CE](Comunicacao-Rede/FTP-CE/)** — sem lógica de FTP implementada apesar do nome; parece teste de conectividade com device Compact Embedded (CE/ARM).

## HMI-Supervisorio

- **[TwinCATHMI](HMI-Supervisorio/TwinCATHMI/)** — eixos (`AXIS_REF`) e NC configurados, mas `MAIN` vazio.
- **[TwinCAT_BSD_CX5240](HMI-Supervisorio/TwinCAT_BSD_CX5240/)** — visualização parcialmente construída (`Home.TcVIS`) em target BSD (CX5240), sem lógica de PLC.
- **[TF2000eMotion](HMI-Supervisorio/TF2000eMotion/)** — apesar do nome sugerir motion, o conteúdo é teste de widgets de HMI (texto/numérico); `MAIN` vazio.

## Safety

- **[SafetyTraining](Safety/SafetyTraining/)** — apenas `.sln`/`.tsproj`, sem sub-projeto Safety anexado.

## Diversos

- **[BeckhoffLinux](Diversos/BeckhoffLinux/)** — casca vazia, aparenta ser teste de conexão com um target TwinCAT/BSD Linux.
- **["TwinCAT - Github - Teste"](<Diversos/TwinCAT - Github - Teste/>)** — `MAIN` é um passthrough trivial (`VarOut := VarIn`); nome e conteúdo indicam teste de integração Git/GitHub, não um exemplo de automação real.
