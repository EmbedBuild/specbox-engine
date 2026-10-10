import 'package:flutter/material.dart';

class ResumenPage extends StatelessWidget {
  const ResumenPage({super.key});

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.disableAnimationsOf(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Propuestas pendientes')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const ListTile(
            title: Text('Reforma cocina Ruiz'),
            trailing: Text('4.800 €', style: TextStyle(fontFeatures: [FontFeature.tabularFigures()])),
          ),
          AnimatedOpacity(
            opacity: 1,
            duration: reduce ? Duration.zero : const Duration(milliseconds: 200),
            curve: Curves.easeOut,
            child: const Text('Abierta 3 veces'),
          ),
          SizedBox(
            height: 48,
            child: FilledButton(onPressed: () {}, child: const Text('Enviar recordatorio')),
          ),
          IconButton(tooltip: 'Filtrar', onPressed: () {}, icon: const Icon(Icons.filter_list)),
        ],
      ),
    );
  }
}
