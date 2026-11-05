# Aplicativo: Wi-Fi livre e administração local por BLE

O app móvel agora lista exclusivamente estações descobertas pelo Bluetooth, sem consultar `/devices` para o scan. Usuários comuns não precisam de conta para alterar Wi-Fi de uma estação provisionada. Login administrativo, TOTP, sessões e provisionamento reutilizam a implementação já existente em `feature/user-accounts`, agora presente nesta cópia de trabalho junto com suas migrações, site e testes.

O intervalo no app é aplicado diretamente no ESP32 via `configure_interval`. O celular não solicita uma configuração remota ao backend. Quando a estação voltar à internet, pode relatar o valor em `POST /devices/config/report`, com sua própria credencial e `source: "ble"`. O backend aceita esse valor apenas se a revisão coincide com a revisão atual do servidor, atualiza o intervalo desejado e o confirmado e registra auditoria. Relatos BLE antigos não sobrescrevem revisões mais recentes do site. Relatos anteriores sem `source` continuam válidos como `remote`.

Atualize backend e firmware antes de validar os relatos BLE. Não há migração adicional além das migrações da base de contas e intervalos reaproveitada. Veja também `app-config-monitoramento-ambiental/README_ACCOUNTS.md` no projeto irmão para preparação do APK e roteiro de teste físico.
