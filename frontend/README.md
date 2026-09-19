# CASA — interface V2

React + Vite + Lucide + Recharts, sem novas dependências de produção.

## Desenvolvimento

Use a branch `front-dev` no repositório CASA. A VM permanece na `main` até a
validação e integração explícita das alterações.

Requer Node.js 22.12+ (ou versão compatível mais recente) e npm.

```bash
cd frontend
npm ci
npm run dev
```

`npm ci` instala todas as dependências do lockfile, incluindo `lucide-react`.
Não é necessário instalar Lucide globalmente. O servidor de desenvolvimento
usa `/api` e encaminha as consultas para `http://127.0.0.1:8000`.

Para consultar o backend já existente na VM durante o desenvolvimento, crie
`frontend/.env.local` (não versionado):

```dotenv
VITE_API_PROXY_TARGET=https://SEU-DOMINIO/api
```

Ou `http://IP-DA-VM/api`, conforme a configuração real do servidor. Reinicie o
Vite após alterar o arquivo. A interface faz apenas GET nas rotas de consulta.
Nunca coloque tokens de estação ou outras credenciais em variáveis `VITE_*`:
elas podem ser incluídas no código enviado ao navegador.

Para abrir no celular na mesma rede:

```bash
npm run dev -- --host 0.0.0.0
```

Acesse `http://IP-DO-COMPUTADOR:5173`. O proxy continua executando no computador;
o telefone não precisa alcançar o backend diretamente. Libere a porta na rede
local se o firewall bloquear. Não use o servidor Vite como servidor público.

## Verificações

```bash
npm test
npm run lint
npm run build
```

Os testes cobrem datas/fusos, horário de verão, paginação acima de 10 mil
registros, erros, cancelamento, escala automática, redução visual e CSV.

## Estrutura

- `src/App.jsx`: composição, estação/aba selecionada e período.
- `src/components`: navegação, filtros, estados de consulta e configurações.
- `src/features`: visão geral, gráfico reutilizável e tabela histórica.
- `src/services/api.js`: contrato da API e histórico paginado.
- `src/hooks/usePolling.js`: consultas com cancelamento e atualização periódica.
- `src/utils`: datas, métricas, exportações e preferências locais.
- `src/styles/dashboard.css`: identidade visual e layouts responsivos.

## Regras de dados

- Fuso padrão: `America/Sao_Paulo`, alterável pela engrenagem e persistido neste
  navegador. Todas as apresentações e filtros seguem o mesmo fuso IANA.
- A troca de fuso reinicia o intervalo para hoje no novo fuso; não altera o banco.
- Datas sem horas incluem os dias completos. Com horas, o último minuto é
  incluído. Internamente usamos início inclusivo e fim exclusivo.
- Horários locais inexistentes em transições de horário de verão são rejeitados.
  Em horários repetidos, a conversão resolve uma das ocorrências; não há seletor
  de ocorrência nesta versão. Dias completos incluem as duas ocorrências.
- A API atual retorna os últimos N registros em ordem crescente, com `end`
  inclusivo. O frontend busca páginas de 1.000, recuando pelo timestamp exato
  do primeiro registro, sobrepondo e removendo duplicatas pelo ID.
- Não há limite arbitrário de 300 registros. A paginação depende da unicidade
  `(device_id, timestamp)` já garantida pelo backend. Intervalos muito extensos
  consomem memória proporcional ao total; exportação por streaming no servidor
  é uma evolução futura. Uma falha em qualquer página impede exportação parcial.
- Gráficos extensos reduzem apenas os pontos desenhados, preservando extremos
  por faixa e indicando a redução. O CSV mantém todos os registros retornados,
  IDs, coordenadas, timestamps originais e precisão numérica original.
- A tabela mostra 50 linhas por página. Isso não limita a consulta nem o CSV.
- Escala Y automática com margem; opção de incluir zero. Valores ausentes
  continuam ausentes, sem substituição por zero.
- O campo `active` indica cadastro habilitado, não conectividade em tempo real.
  Última comunicação e última medição são mostradas separadamente.
- Exportação PNG inclui título, estação, período, séries e fuso.

## Identidade e próximas etapas

A paleta usa branco, turquesa e azul-marinho da referência T2P. O cabeçalho usa
uma assinatura tipográfica provisória, não o arquivo oficial da marca. Substitua
pela logo original SVG/PNG sem os controles de navegação presentes no print.

Login, autorização por estação e administração continuam previstos para a V3.
O ícone de usuário apenas reserva seu lugar no canto superior esquerdo.
As permissões deverão ser verificadas pelo backend, nunca somente pela interface.

Não há alteração de banco, backend, Compose ou configuração da VM nesta V2.
Teste com dados reais e confirme o visual no telefone antes do merge/deploy.
