from rest_framework.filters import BaseFilterBackend
from django.core import exceptions
import logging

logger = logging.getLogger(__name__)


class BaseFilter(BaseFilterBackend):
    def __init__(self):
        self.errors = {}

    def filter_queryset(self, request, queryset, view):
        params = self.parse_query_params(request, queryset)
        self.queryset = queryset
        for key, value in params.items():
            local_vars = {"value": value, "self": self}
            try:
                exec(f"self.queryset=self.queryset.filter({key}=value)", globals(), local_vars)
            except exceptions.ValidationError as e:
                self.errors[key] = "Valor inválido!"
                logger.info(e, self.errors)
            except exceptions.FieldError as e:
                self.errors[key] = "Esse campo não existe!"
                logger.info(e, self.errors)
            except Exception as e:
                self.errors[key] = "Erro ao filtrar os objetos. Confira os parâmetros passados!"
                logger.info(e, self.errors)
        return self.queryset

    def parse_query_params(self, request, queryset):
        params = {}
        for key, value in request.query_params.items():
            try:
                if value.replace(',', '').replace('.', '').isnumeric():
                    value = float(value) if not float(value).is_integer() else int(float(value))
                elif value.upper() in ['NÃO', 'NAO', 'FALSE']:
                    value = False
                elif value.upper() in ['SIM', 'TRUE']:
                    value = True
            except Exception as e:
                logger.info(e)
            else:
                params[key] = value
        if 'page' in params.keys():
            del params['page']
        return params
