import numpy as np
from qiskit import QuantumCircuit, execute, Aer

# Anzahl der zu sendenden Qubits
num_qubits = 100

# Alice erzeugt zufällige Bits und Basen
alice_bits = np.random.randint(2, size=num_qubits)  # 0 oder 1
alice_bases = np.random.randint(2, size=num_qubits)  # 0 = Standardbasis, 1 = Hadamardbasis

# Erstellen eines Quantenkreises
quantum_circuit = QuantumCircuit(num_qubits, num_qubits)

# Kodierung der Qubits basierend auf Alices Bits und Basen
for i in range(num_qubits):
    if alice_bits[i] == 1:
        quantum_circuit.x(i)  # X-Gate, um das Bit 1 zu setzen
    if alice_bases[i] == 1:
        quantum_circuit.h(i)  # Hadamard-Gate, um in die Hadamardbasis zu wechseln

# Simulation der Übertragung der Qubits
simulator = Aer.get_backend('qasm_simulator')
quantum_circuit.measure(range(num_qubits), range(num_qubits))
result = execute(quantum_circuit, simulator, shots=1).result()
counts = result.get_counts()

print("Alices zufällige Bits: ", alice_bits)
print("Alices zufällige Basen: ", alice_bases)



# Bobs zufällige Messbasen
bob_bases = np.random.randint(2, size=num_qubits)  # Bob wählt zufällige Basen

# Simulation von Bobs Messung
quantum_circuit.measure(range(num_qubits), range(num_qubits))
result = execute(quantum_circuit, simulator, shots=1).result()
bob_measurements = result.get_counts()

# Umwandlung der Messungen in Bobs gemessene Bits
bob_bits = np.zeros(num_qubits)
for i, bit in enumerate(bob_measurements.keys()):
    bob_bits[i] = int(bit[0])

# Schlüsselabgleich: Nur wenn Alice und Bob die gleiche Basis verwenden, nehmen sie das Bit in den Schlüssel auf
shared_key = []
for i in range(num_qubits):
    if alice_bases[i] == bob_bases[i]:
        shared_key.append(alice_bits[i])

print("Bobs zufällige Basen: ", bob_bases)
print("Gemeinsamer Schlüssel: ", shared_key)




# Eve misst die Qubits, bevor sie bei Bob ankommen
eve_bases = np.random.randint(2, size=num_qubits)  # Eve wählt zufällige Basen

# Simulation von Eves Messung
quantum_circuit.measure(range(num_qubits), range(num_qubits))
result = execute(quantum_circuit, simulator, shots=1).result()
eve_measurements = result.get_counts()

# Umwandlung der Messungen in Eves gemessene Bits
eve_bits = np.zeros(num_qubits)
for i, bit in enumerate(eve_measurements.keys()):
    eve_bits[i] = int(bit[0])

# Effekt auf Bobs Messung: Durch Eves Eingreifen können sich die Bits ändern
bob_bits_after_eve = np.zeros(num_qubits)
for i in range(num_qubits):
    if eve_bases[i] == bob_bases[i]:
        bob_bits_after_eve[i] = alice_bits[i]
    else:
        bob_bits_after_eve[i] = np.random.randint(2)  # Messfehler durch Eves Eingriff

# Schlüsselabgleich nach Eves Eingriff
shared_key_after_eve = []
for i in range(num_qubits):
    if alice_bases[i] == bob_bases[i]:
        shared_key_after_eve.append(bob_bits_after_eve[i])

print("Eves zufällige Basen: ", eve_bases)
print("Gemeinsamer Schlüssel nach Eves Eingriff: ", shared_key_after_eve)
