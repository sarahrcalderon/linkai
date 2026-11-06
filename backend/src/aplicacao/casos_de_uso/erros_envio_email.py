class FalhaEnvioEmail(Exception):
    """Erro interno neutro; não contém resposta, destinatário ou credenciais do provedor."""


class ConfiguracaoEnvioInvalida(FalhaEnvioEmail):
    def __init__(self) -> None:
        super().__init__("Configure o serviço de e-mail antes de utilizá-lo.")


class EnvioEmailPermanente(FalhaEnvioEmail):
    def __init__(self) -> None:
        super().__init__("Não foi possível aceitar a solicitação de e-mail.")


class EnvioEmailTemporario(FalhaEnvioEmail):
    def __init__(self, aguardar_segundos: float | None = None) -> None:
        self.aguardar_segundos = aguardar_segundos
        super().__init__("Serviço de e-mail temporariamente indisponível.")


class EnvioEmailIndeterminado(FalhaEnvioEmail):
    def __init__(self) -> None:
        super().__init__("Não foi possível confirmar a aceitação do e-mail.")
