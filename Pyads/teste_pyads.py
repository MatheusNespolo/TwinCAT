# Exemplo prático — lendo e escrevendo uma variável
import pyads

# Criação da rota (opcional)
# pyads.add_route_to_plc(
#     sending_net_id="192.168.88.1.1.1",  # AmsNetId do PC com Python
#     adding_host_name="169.254.220.126",     # IP do PC com Python
#     ip_address="169.254.56.204",           # IP do controlador TwinCAT
#     username="Administrator",
#     password="1",
#     route_name="rota-python"
# )

# Conexão com o PLC (porta 851 = primeiro Runtime de PLC)
plc = pyads.Connection("5.162.186.144.1.1", pyads.PORT_TC3PLC1)

#AMS NetId do controlador TwinCAT, porta 851
plc.open()

# Leitura de uma variável declarada em uma GVL
valor = plc.read_by_name("GVL.Contador")
print(f"Valor atual: {valor}")

# Escrita de uma variável
plc.write_by_name("GVL.SetpointVelocidade", 42.0)

plc.close()
