// Contenido estático de la sección «DSA y recursos».
// El pseudocódigo usa las mismas palabras clave que el conversor, así se puede convertir directamente.

window.DSA = [
  {
    name: "Búsqueda binaria",
    category: "Búsqueda",
    complexity: "O(log n) · O(1)",
    when: "Datos ordenados, o cualquier pregunta «¿cuál es el menor x que cumple…?» sobre una función monótona.",
    pseudo: `FUNCION busqueda_binaria(lista, objetivo)
  izq <- 0
  der <- LONGITUD(lista) - 1
  MIENTRAS izq <= der HACER
    medio <- (izq + der) DIV 2
    SI lista[medio] = objetivo ENTONCES
      RETORNAR medio
    SINO SI lista[medio] < objetivo ENTONCES
      izq <- medio + 1
    SINO
      der <- medio - 1
    FIN SI
  FIN MIENTRAS
  RETORNAR -1
FIN FUNCION`,
  },
  {
    name: "Dos punteros",
    category: "Arreglos",
    complexity: "O(n) · O(1)",
    when: "Pares que suman un objetivo en un arreglo ordenado, invertir, quitar duplicados, palíndromos.",
    pseudo: `FUNCION par_con_suma(lista_ordenada, objetivo)
  i <- 0
  j <- LONGITUD(lista_ordenada) - 1
  MIENTRAS i < j HACER
    suma <- lista_ordenada[i] + lista_ordenada[j]
    SI suma = objetivo ENTONCES
      RETORNAR (i, j)
    SINO SI suma < objetivo ENTONCES
      i <- i + 1
    SINO
      j <- j - 1
    FIN SI
  FIN MIENTRAS
  RETORNAR NULO
FIN FUNCION`,
  },
  {
    name: "Ventana deslizante",
    category: "Arreglos",
    complexity: "O(n) · O(k)",
    when: "Subarreglos o subcadenas contiguas: máxima suma de tamaño k, subcadena más larga sin repetidos.",
    pseudo: `FUNCION subcadena_mas_larga_sin_repetir(texto)
  vistos <- MAPA vacío
  inicio <- 0
  mejor <- 0
  PARA fin DESDE 0 HASTA LONGITUD(texto) - 1 HACER
    c <- texto[fin]
    SI c EN vistos Y vistos[c] >= inicio ENTONCES
      inicio <- vistos[c] + 1
    FIN SI
    vistos[c] <- fin
    mejor <- MAXIMO(mejor, fin - inicio + 1)
  FIN PARA
  RETORNAR mejor
FIN FUNCION`,
  },
  {
    name: "Suma de prefijos",
    category: "Arreglos",
    complexity: "O(n) preparar · O(1) consulta",
    when: "Muchas consultas de suma en rangos [a, b]; subarreglos con suma k (junto con un mapa).",
    pseudo: `FUNCION prefijos(lista)
  pref <- ARREGLO de tamaño LONGITUD(lista) + 1 con ceros
  PARA i DESDE 0 HASTA LONGITUD(lista) - 1 HACER
    pref[i + 1] <- pref[i] + lista[i]
  FIN PARA
  RETORNAR pref
FIN FUNCION

FUNCION suma_rango(pref, a, b)
  RETORNAR pref[b + 1] - pref[a]
FIN FUNCION`,
  },
  {
    name: "Mapa hash (conteo / complemento)",
    category: "Hashing",
    complexity: "O(n) · O(n)",
    when: "Two-sum sin ordenar, frecuencias, anagramas, detectar duplicados en una pasada.",
    pseudo: `FUNCION two_sum(lista, objetivo)
  indice <- MAPA vacío
  PARA i DESDE 0 HASTA LONGITUD(lista) - 1 HACER
    falta <- objetivo - lista[i]
    SI falta EN indice ENTONCES
      RETORNAR (indice[falta], i)
    FIN SI
    indice[lista[i]] <- i
  FIN PARA
  RETORNAR NULO
FIN FUNCION`,
  },
  {
    name: "Merge sort",
    category: "Ordenamiento",
    complexity: "O(n log n) · O(n)",
    when: "Ordenamiento estable garantizado; base de «contar inversiones» y de ordenar listas enlazadas.",
    pseudo: `FUNCION merge_sort(lista)
  SI LONGITUD(lista) <= 1 ENTONCES
    RETORNAR lista
  FIN SI
  medio <- LONGITUD(lista) DIV 2
  izq <- merge_sort(lista[0 .. medio - 1])
  der <- merge_sort(lista[medio .. FIN])
  resultado <- LISTA vacía
  i <- 0
  j <- 0
  MIENTRAS i < LONGITUD(izq) Y j < LONGITUD(der) HACER
    SI izq[i] <= der[j] ENTONCES
      AGREGAR izq[i] A resultado
      i <- i + 1
    SINO
      AGREGAR der[j] A resultado
      j <- j + 1
    FIN SI
  FIN MIENTRAS
  AGREGAR el resto de izq y de der A resultado
  RETORNAR resultado
FIN FUNCION`,
  },
  {
    name: "Quick sort",
    category: "Ordenamiento",
    complexity: "O(n log n) prom. · O(n²) peor",
    when: "Ordenar en el mismo arreglo; su partición sirve para «k-ésimo menor» (quickselect).",
    pseudo: `FUNCION quick_sort(lista, bajo, alto)
  SI bajo < alto ENTONCES
    pivote <- lista[alto]
    i <- bajo - 1
    PARA j DESDE bajo HASTA alto - 1 HACER
      SI lista[j] <= pivote ENTONCES
        i <- i + 1
        INTERCAMBIAR lista[i] CON lista[j]
      FIN SI
    FIN PARA
    INTERCAMBIAR lista[i + 1] CON lista[alto]
    quick_sort(lista, bajo, i)
    quick_sort(lista, i + 2, alto)
  FIN SI
FIN FUNCION`,
  },
  {
    name: "Pila monótona",
    category: "Pilas y colas",
    complexity: "O(n) · O(n)",
    when: "«Siguiente elemento mayor», temperaturas diarias, área máxima en histograma, validar paréntesis.",
    pseudo: `FUNCION siguiente_mayor(lista)
  resultado <- ARREGLO de tamaño LONGITUD(lista) con -1
  pila <- PILA vacía
  PARA i DESDE 0 HASTA LONGITUD(lista) - 1 HACER
    MIENTRAS pila NO vacía Y lista[TOPE(pila)] < lista[i] HACER
      resultado[SACAR(pila)] <- lista[i]
    FIN MIENTRAS
    METER i EN pila
  FIN PARA
  RETORNAR resultado
FIN FUNCION`,
  },
  {
    name: "BFS (búsqueda en anchura)",
    category: "Grafos",
    complexity: "O(V + E) · O(V)",
    when: "Camino más corto en grafos sin pesos, niveles de un árbol, laberintos, propagación por capas.",
    pseudo: `FUNCION bfs(grafo, origen)
  distancia <- MAPA vacío
  distancia[origen] <- 0
  cola <- COLA con origen
  MIENTRAS cola NO vacía HACER
    nodo <- DESENCOLAR(cola)
    PARA CADA vecino EN grafo[nodo] HACER
      SI NO (vecino EN distancia) ENTONCES
        distancia[vecino] <- distancia[nodo] + 1
        ENCOLAR vecino EN cola
      FIN SI
    FIN PARA
  FIN MIENTRAS
  RETORNAR distancia
FIN FUNCION`,
  },
  {
    name: "DFS (búsqueda en profundidad)",
    category: "Grafos",
    complexity: "O(V + E) · O(V)",
    when: "Componentes conexas, detectar ciclos, contar islas, recorrer todo lo alcanzable.",
    pseudo: `FUNCION contar_islas(mapa)
  islas <- 0
  PARA f DESDE 0 HASTA FILAS(mapa) - 1 HACER
    PARA c DESDE 0 HASTA COLUMNAS(mapa) - 1 HACER
      SI mapa[f][c] = 1 ENTONCES
        islas <- islas + 1
        hundir(mapa, f, c)
      FIN SI
    FIN PARA
  FIN PARA
  RETORNAR islas
FIN FUNCION

FUNCION hundir(mapa, f, c)
  SI f < 0 O c < 0 O f >= FILAS(mapa) O c >= COLUMNAS(mapa) O mapa[f][c] <> 1 ENTONCES
    RETORNAR
  FIN SI
  mapa[f][c] <- 0
  hundir(mapa, f + 1, c)
  hundir(mapa, f - 1, c)
  hundir(mapa, f, c + 1)
  hundir(mapa, f, c - 1)
FIN FUNCION`,
  },
  {
    name: "Dijkstra",
    category: "Grafos",
    complexity: "O((V + E) log V) · O(V)",
    when: "Camino más corto con pesos no negativos: rutas, redes, costos mínimos.",
    pseudo: `FUNCION dijkstra(grafo, origen)
  dist <- MAPA con INFINITO para cada nodo
  dist[origen] <- 0
  monticulo <- COLA DE PRIORIDAD con (0, origen)
  MIENTRAS monticulo NO vacío HACER
    (d, nodo) <- SACAR_MINIMO(monticulo)
    SI d > dist[nodo] ENTONCES
      CONTINUAR
    FIN SI
    PARA CADA (vecino, peso) EN grafo[nodo] HACER
      SI d + peso < dist[vecino] ENTONCES
        dist[vecino] <- d + peso
        INSERTAR (dist[vecino], vecino) EN monticulo
      FIN SI
    FIN PARA
  FIN MIENTRAS
  RETORNAR dist
FIN FUNCION`,
  },
  {
    name: "Orden topológico (Kahn)",
    category: "Grafos",
    complexity: "O(V + E) · O(V)",
    when: "Dependencias: orden de compilación, prerrequisitos de cursos, pipelines; detecta ciclos.",
    pseudo: `FUNCION orden_topologico(grafo)
  grado <- MAPA con 0 para cada nodo
  PARA CADA nodo EN grafo HACER
    PARA CADA vecino EN grafo[nodo] HACER
      grado[vecino] <- grado[vecino] + 1
    FIN PARA
  FIN PARA
  cola <- COLA con los nodos de grado 0
  orden <- LISTA vacía
  MIENTRAS cola NO vacía HACER
    nodo <- DESENCOLAR(cola)
    AGREGAR nodo A orden
    PARA CADA vecino EN grafo[nodo] HACER
      grado[vecino] <- grado[vecino] - 1
      SI grado[vecino] = 0 ENTONCES
        ENCOLAR vecino EN cola
      FIN SI
    FIN PARA
  FIN MIENTRAS
  SI LONGITUD(orden) <> LONGITUD(grafo) ENTONCES
    IMPRIMIR "Hay un ciclo"
  FIN SI
  RETORNAR orden
FIN FUNCION`,
  },
  {
    name: "Union-Find (conjuntos disjuntos)",
    category: "Grafos",
    complexity: "≈ O(1) amortizado por operación",
    when: "Agrupar elementos conectados, árbol de expansión mínima (Kruskal), detectar ciclos en grafos no dirigidos.",
    pseudo: `FUNCION buscar(padre, x)
  SI padre[x] <> x ENTONCES
    padre[x] <- buscar(padre, padre[x])
  FIN SI
  RETORNAR padre[x]
FIN FUNCION

FUNCION unir(padre, a, b)
  raiz_a <- buscar(padre, a)
  raiz_b <- buscar(padre, b)
  SI raiz_a = raiz_b ENTONCES
    RETORNAR FALSO
  FIN SI
  padre[raiz_b] <- raiz_a
  RETORNAR VERDADERO
FIN FUNCION`,
  },
  {
    name: "Montículo / Top-K",
    category: "Montículos",
    complexity: "O(n log k) · O(k)",
    when: "Los k mayores o más frecuentes, mediana en flujo, mezclar k listas ordenadas.",
    pseudo: `FUNCION k_mayores(lista, k)
  monticulo <- MONTICULO DE MINIMOS vacío
  PARA CADA x EN lista HACER
    INSERTAR x EN monticulo
    SI TAMAÑO(monticulo) > k ENTONCES
      SACAR_MINIMO(monticulo)
    FIN SI
  FIN PARA
  RETORNAR elementos de monticulo
FIN FUNCION`,
  },
  {
    name: "Programación dinámica",
    category: "Programación dinámica",
    complexity: "O(n · m) típico",
    when: "Subproblemas que se repiten: mochila, cambio de monedas, subsecuencia común más larga, caminos en grilla.",
    pseudo: `FUNCION cambio_minimo(monedas, monto)
  dp <- ARREGLO de tamaño monto + 1 con INFINITO
  dp[0] <- 0
  PARA valor DESDE 1 HASTA monto HACER
    PARA CADA m EN monedas HACER
      SI m <= valor Y dp[valor - m] + 1 < dp[valor] ENTONCES
        dp[valor] <- dp[valor - m] + 1
      FIN SI
    FIN PARA
  FIN PARA
  SI dp[monto] = INFINITO ENTONCES
    RETORNAR -1
  FIN SI
  RETORNAR dp[monto]
FIN FUNCION`,
  },
  {
    name: "Backtracking",
    category: "Recursión",
    complexity: "Exponencial (con poda)",
    when: "Generar todas las combinaciones, permutaciones o subconjuntos; N-reinas, sudoku.",
    pseudo: `FUNCION subconjuntos(lista)
  resultado <- LISTA vacía
  explorar(lista, 0, LISTA vacía, resultado)
  RETORNAR resultado
FIN FUNCION

FUNCION explorar(lista, i, actual, resultado)
  SI i = LONGITUD(lista) ENTONCES
    AGREGAR COPIA(actual) A resultado
    RETORNAR
  FIN SI
  AGREGAR lista[i] A actual
  explorar(lista, i + 1, actual, resultado)
  QUITAR el último de actual
  explorar(lista, i + 1, actual, resultado)
FIN FUNCION`,
  },
  {
    name: "Trie (árbol de prefijos)",
    category: "Árboles",
    complexity: "O(L) por palabra",
    when: "Autocompletar, búsqueda por prefijo, diccionarios, palabras en una sopa de letras.",
    pseudo: `FUNCION insertar(raiz, palabra)
  nodo <- raiz
  PARA CADA letra EN palabra HACER
    SI NO (letra EN nodo.hijos) ENTONCES
      nodo.hijos[letra] <- NUEVO NODO
    FIN SI
    nodo <- nodo.hijos[letra]
  FIN PARA
  nodo.es_palabra <- VERDADERO
FIN FUNCION

FUNCION tiene_prefijo(raiz, prefijo)
  nodo <- raiz
  PARA CADA letra EN prefijo HACER
    SI NO (letra EN nodo.hijos) ENTONCES
      RETORNAR FALSO
    FIN SI
    nodo <- nodo.hijos[letra]
  FIN PARA
  RETORNAR VERDADERO
FIN FUNCION`,
  },
];

// Documentación oficial de cada lenguaje del conversor (id = id del backend).
window.LANGUAGE_DOCS = [
  { id: "python", name: "Python 3", links: [
    ["Documentación oficial", "https://docs.python.org/3/"],
    ["Biblioteca estándar", "https://docs.python.org/3/library/index.html"],
  ] },
  { id: "go", name: "Go", links: [
    ["Documentación", "https://go.dev/doc/"],
    ["Especificación del lenguaje", "https://go.dev/ref/spec"],
    ["Biblioteca estándar", "https://pkg.go.dev/std"],
  ] },
  { id: "typescript", name: "TypeScript / Node.js", links: [
    ["Handbook de TypeScript", "https://www.typescriptlang.org/docs/"],
    ["API de Node.js", "https://nodejs.org/docs/latest/api/"],
  ] },
  { id: "java", name: "Java 21", links: [
    ["Documentación Java SE 21", "https://docs.oracle.com/en/java/javase/21/"],
    ["API Java SE 21", "https://docs.oracle.com/en/java/javase/21/docs/api/index.html"],
  ] },
  { id: "csharp", name: "C# / .NET", links: [
    ["Guía de C#", "https://learn.microsoft.com/es-es/dotnet/csharp/"],
    ["API de .NET", "https://learn.microsoft.com/es-es/dotnet/api/"],
  ] },
  { id: "vbnet", name: "Visual Basic .NET", links: [
    ["Guía de Visual Basic", "https://learn.microsoft.com/es-es/dotnet/visual-basic/"],
  ] },
  { id: "asp", name: "ASP Classic", links: [
    ["Objetos integrados de ASP (archivo Microsoft)", "https://learn.microsoft.com/en-us/previous-versions/aa711478(v=vs.71)"],
  ] },
  { id: "rpgle", name: "IBM i (AS400) · RPGLE", links: [
    ["ILE RPG Reference (IBM i 7.5)", "https://www.ibm.com/docs/en/ssw_ibm_i_75/rzasd/rzasdmain.htm"],
    ["PUB400 · IBM i gratuito para practicar", "https://pub400.com/"],
  ] },
];

window.EXTRA_RESOURCES = [
  ["VisuAlgo", "https://visualgo.net/", "animaciones de estructuras de datos y algoritmos"],
  ["CP-Algorithms", "https://cp-algorithms.com/", "explicaciones detalladas de algoritmos clásicos"],
  ["Big-O Cheat Sheet", "https://www.bigocheatsheet.com/", "complejidades de un vistazo"],
  ["NeetCode Roadmap", "https://neetcode.io/roadmap", "ruta de problemas por patrón"],
  ["MIT 6.006 Introduction to Algorithms", "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/", "curso abierto completo"],
];
