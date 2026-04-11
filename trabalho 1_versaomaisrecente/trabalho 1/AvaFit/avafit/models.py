from django.db import models

class AvaFit(models.Model):  
    nome = models.CharField(max_length=100, default="Minha AvaFit")
    saude = models.IntegerField(default=100)
    passos_hoje = models.IntegerField(default=0)
    estado = models.CharField(max_length=50, default="Feliz")
    
    def __str__(self):
        return self.nome
