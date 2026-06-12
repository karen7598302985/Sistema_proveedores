# gestion de proveedores 

Sistema web para registrar y gestionar proveedores, tiene dos formas de cargar datos: manual desde un formulario, o automatica subiendo un archivo que procesa 
un robot por separado.

las tecnologias que utilice fueron:
-Backend: python con fastAPI
-Base de datos: SQlite
-Frondend: HTML, CSS y javascript puro sin frameworks
-Robot RPA: Script python independiente usando pandas 

decidi elegir FastApi porque tiene validacion de base de datos integrada con pydantic, lo que me facilita controlar que los campos lleguen bien formados sin escribir mucho codigo.SQLite lo use porque para este caso no necesitaba un servidor de base de datos separado ademas me parece facil de usar.

# Estructura

proyect/
|-bakend/
| |-main.py
|  |-requirements.txt
|  |-database/
|  |_ uploads/
|--frondend/
   |_index.html
|-robot/
  |-robot.py
  |-proveedores_prueba.csv
|-database/
  |-schema.sql
|
|-README.md

# correrlo
Instale python 3.12
verifique que estuviera instalado con 
python --version

luego instale las dependencias, dentro de la carpera de bakend instale la dependencia de requirements.txt con 
pip install -r requirements.txt

levante el backend, desde la misma carpeta de bakend ingrese 
python - m uvicorn main:app --reload --port 8000

donde se ejecuto correctamente y ingrese al link 
http://127.0.0.1:8000

la primera vez que corre crea sola la base de datos y las tablas usando schema.sql

luego abri el link en el navegador.

luego corri el robot,ingresando a la terminal sin cerrar la pestaña donde se ejecuta la base de datos,  dentro de la carpeta del robot colocque : python robot.py

el robot se queda esperando y cuando detecta el archivo lo procesa automaticamente, para detnerlo con  Ctrl+c

# comprobar flujos 

el flujo manual, que es llenar el formulario con los campos NIT,nombre, pais y estado.
clic en registrar, el proveedor aparece automaticamente en la tabla con el origen manual 

el flujo automatico, que es basicamente subir el archivo realizo desde excel, desde la seccion de carga automatica, el indicador cambia a procesando y el robot detecta en unos segundos, valida cada fila y la inserta.
y la tabla se actualiza sola y aparecen los proveedores con origen automatico. 

adicional cualquier proveedor de la tabla tiene un boton de editar, solo se puede cambiar nombre o estado de inactividad, el nit no se toca. 

# endpoindt disponibles 

POST : /api/proveedores/manual - resgistrar proveedor desde el formulario 

POST : /api/proveedores/upload-archivo - subir el archivo para el robot

GET: /api/proveedores - traer todo los proveedores

PUT: /api/proveedores/{id} editar nombre o estado 

GET: /api/proveedores/archivo-estado/{id} - ver en que estado esta el archivo subido 

GET: /api/robot/archivo-pendiente - el robot pregunta si hay trabajo 

POST: /api/robot/insertar-masivo - el robot manda los datos para guardar 

la documentacion interactiva de la API queda disponible en http://localhost:8000/docs

# formato de archivo excel CSV

las columnas que debe tener el archivo son exactamente: 

nit_empresa, nombre_empresa, pais, estado_registro

el campo estado_registro solo acepta ACTIVO o INACTIVO. si una fila tiene ese campo diferente el robot la descarta y sigue con las demás

# algo importante sobre la concurrencia 

un caso que tuve que resolver fue que pasa si el usuario edita el proveedor mientras el robot se esta ejecuetando al mismo tiempo, para evitar bloqueo entre si configure SQLite en modo Wal (Write-Ahead Logging), que permite lecturas y escrituras simultaneas sin que uno espere al otro. 

adicional, el robot no conecta con el backend
Verificar que el backend esté corriendo antes de lanzar el robot.

