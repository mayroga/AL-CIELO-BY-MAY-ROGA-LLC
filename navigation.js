// Motor de Navegación "AL CIELO"
class NavegadorOffline {
    constructor(mapData) {
        this.mapa = mapData; // Mapa de toda Cuba cargado localmente
        this.recalculando = false;
    }

    onLocationChange(currentPos) {
        if (this.estaFueraDeRuta(currentPos) && !this.recalculando) {
            this.recalculando = true;
            this.reproducirVoz("Recalculando ruta");
            this.calcularNuevaRuta(currentPos, this.destinoFinal);
        }
    }

    reproducirVoz(texto) {
        const msg = new SpeechSynthesisUtterance(texto);
        msg.lang = 'es-ES';
        window.speechSynthesis.speak(msg);
    }
}
