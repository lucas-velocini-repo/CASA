# Atualização dos testes: intervalos, login e aplicativo

Esta etapa continua os testes já feitos com contas. Preserve `.env.teste`, a chave de
criptografia, o volume PostgreSQL e as contas existentes. Não recrie o administrador.
As alterações estão nas branches `feature/user-accounts` do CASA e do aplicativo;
o firmware está em `feature/remote-interval`.

## Atualizar o ambiente local existente

Na pasta do CASA usada nos testes:

```bash
git switch feature/user-accounts
git pull --ff-only origin feature/user-accounts
```

Se necessário, redefina a função do terminal:

```bash
cteste() {
  docker compose --env-file .env.teste -p casa-teste -f compose.teste.yaml "$@"
}
```

Compile, aplique a migração adicional e atualize os serviços:

```bash
cteste build backend frontend mail-worker
cteste run --rm backend alembic upgrade head
cteste up -d
cteste ps
```

A tabela adicional guarda configurações das estações. Não altera medições nem vínculos.
Abra novamente o mesmo endereço configurado em `PUBLIC_APP_URL`. O login mostra o
campo TOTP/recuperação ao clicar **Sou administrador**. Ativação e redefinição de
senhas agora aceitam de 8 a 128 caracteres. Senhas anteriores continuam funcionando.

## Instalar o app atualizado

Na cópia de testes do repositório do aplicativo:

```bash
git switch feature/user-accounts
git pull --ff-only origin feature/user-accounts
npm ci
npm test
npx tsc --noEmit
npm run lint
```

Mantenha `.env.local` apontando ao IP do computador e `APP_VARIANT=development`, como
no guia principal. Ao testar na rede local, o celular precisa alcançar esse endereço.
O gerenciamento por rede do aplicativo também funciona à distância quando usa a
API HTTPS publicada; o Bluetooth continua exigindo proximidade física.

Para incorporar também o nome/splash nativos atualizados:

```bash
npx eas-cli build --platform android --profile development
```

Instale o novo APK de desenvolvimento e execute:

```bash
npx expo start --dev-client --lan
```

Telas agora compartilham a logo T2P usada no site, identificação CASA, fundo claro,
paleta azul e cartões/formulários consistentes. A tela inicial administrativa separa
estações próximas por Bluetooth e estações cadastradas acessíveis pela rede.

## Testar Bluetooth antes de atualizar o firmware

1. Ligue duas estações e entre no app como administrador.
2. Confira o identificador Bluetooth de cada cartão; nomes ausentes recebem um
   identificador de fallback. Anúncios posteriores com nome atualizam a mesma linha.
3. Abra uma estação, pressione **voltar do Android**, aguarde o retorno e conecte de novo.
4. Repita usando o botão voltar do app e **Concluir e desconectar**.
5. Passe do cadastro para Wi-Fi e confirme que a conexão permanece nesse fluxo.
6. Saia da conta, conecte novamente e simule falha de conexão/desligamento da estação.

Ao voltar à lista a conexão nativa é cancelada antes do novo scan. A estação precisa
estar alimentada e voltar a anunciar. O firmware novo envia um nome único no scan;
unidades antigas ainda podem apresentar o nome genérico anterior, acompanhado do ID.

## Preparar uma estação de bancada

Atualize o servidor de testes primeiro. No repositório do firmware:

```bash
git fetch origin
git switch feature/remote-interval
git pull --ff-only origin feature/remote-interval
pio run
pio run --target upload
```

Ajuste `upload_port` à porta real no PlatformIO local. Verifique a pinagem existente
na sua montagem antes de gravar. Não apague a flash/NVS/LittleFS; preserve as
credenciais e a fila. Use uma estação de bancada antes de atualizar unidades em casas.
Ela deve apontar para o servidor de testes, sem reutilizar credencial de produção em
outro banco. Se precisar de novo cadastro, use o fluxo normal do app.

O padrão do firmware sem intervalo salvo é 300 s. O servidor não envia um intervalo
arbitrário antes de uma solicitação administrativa; apenas registra o valor informado
pela estação compatível. Firmware anterior permanece enviando no intervalo anterior,
com a configuração aparecendo sem confirmação.

## Testar o intervalo de ponta a ponta

1. No site, abra **Administração → Estações**. Confira o intervalo confirmado ou a
   mensagem de que falta um firmware compatível.
2. Na estação de bancada, informe **60** segundos e clique **Solicitar intervalo**.
3. Confira o estado **pendente**. Em condições normais, a estação consulta a API a cada
   minuto, salva a configuração e o painel muda para **aplicado** após atualizar os dados.
   O painel e o app atualizam seus dados a cada 30 segundos.
4. Espere pelo menos três medições novas e compare os timestamps; o intervalo deve
   ficar próximo de 60 s. A primeira medição após a mudança pode ocorrer em um período
   de transição, pois depende do tempo já transcorrido desde a última aquisição.
5. Reinicie a estação e confira que ela mantém 60 s.
6. Interrompa o Wi-Fi da estação ou pare somente o backend. Solicite **120** segundos
   quando o servidor estiver acessível, deixando a estação offline: deve ficar pendente.
7. Reconecte a estação e confirme a aplicação de 120 s e o reenvio da fila com horários
   originais. O intervalo não altera os timestamps históricos.
8. No app administrativo, em **Estações cadastradas · Rede**, toque **Alterar intervalo
   pela rede** e solicite **300** segundos. Não é preciso conectar por BLE.
9. Confirme no site que o mesmo comando chegou e foi aplicado. Repita no sentido inverso.
10. Com conta comum, confirme que nenhum controle de intervalo aparece e a API retorna
    403 ao tentar uma alteração administrativa.

Limites: de 30 a 86400 segundos, inteiros. A aquisição e o envio periódico passam a usar
o novo intervalo. A agenda diária do GPS e a cadência de reenvio da fila não mudam.
O indicador de atividade do site considera o intervalo confirmado (tolerância de 20%,
com piso de seis minutos), evitando mostrar uma estação como inativa entre aquisições
programadas mais longas. A confirmação mostra a hora do último reporte, sem garantir
que uma estação continue conectada depois dessa hora.

## Implantação posterior

Continue o procedimento de backup/implantação do guia principal. O servidor deve ser
atualizado antes do firmware. O recurso exige a migração `d720interval01` após a migração
das contas. Caso use `Caddyfile.http-ingestion` temporariamente, atualize também esse
arquivo: agora permite GET `/api/devices/config` e POST `/api/devices/config/report`,
ambos com autenticação de estação, além dos caminhos de ingestão existentes.
A compatibilidade HTTP não cifra credenciais; mantenha o plano de migração para HTTPS.

Atualizar somente site/app não atualiza as estações: o novo firmware precisa ser gravado
uma vez por cabo. Mudanças futuras do **intervalo** usam a rede; não foi implementado OTA.
Faça merge do PR do firmware para `main` somente depois do teste de bancada.
