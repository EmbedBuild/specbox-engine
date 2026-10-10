import 'package:flutter/material.dart';

class PropuestasPage extends StatefulWidget {
  const PropuestasPage({super.key});

  @override
  State<PropuestasPage> createState() => _PropuestasPageState();
}

class _PropuestasPageState extends State<PropuestasPage> {
  bool visible = true;

  @override
  Widget build(BuildContext context) {
    return MediaQuery.withNoTextScaling(
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Propuestas pendientes'),
          actions: [
            IconButton(
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
              icon: const Icon(Icons.filter_list),
              onPressed: () {},
            ),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Row(
              children: [
                SizedBox(width: 220, child: Text('Reforma cocina Ruiz')),
                SizedBox(width: 220, child: Text('4.800 €')),
              ],
            ),
            AnimatedOpacity(
              opacity: visible ? 1 : 0,
              duration: const Duration(milliseconds: 600),
              curve: Curves.easeIn,
              child: const Text('Abierta 3 veces · 9 min de lectura'),
            ),
            TextButton(
              style: TextButton.styleFrom(tapTargetSize: MaterialTapTargetSize.shrinkWrap),
              onPressed: () {},
              child: const Text('Enviar recordatorio'),
            ),
            IconButton(onPressed: () {}, icon: const Text('🚀')),
          ],
        ),
      ),
    );
  }
}
