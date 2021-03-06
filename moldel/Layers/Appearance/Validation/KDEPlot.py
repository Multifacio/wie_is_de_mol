from Layers.Appearance.AppearanceLayer import InnerAppearanceLayer
from Layers.Appearance.AppearanceExtractor import AppearanceExtractor
from scipy.stats import mannwhitneyu
import matplotlib.pyplot as plt
import numpy as np

TEST_SEASONS = {13, 14, 15, 16, 17, 18, 19, 20}
AUGMENTATION_CUTS = 4
AUGMENTATION_MIN_CUTS_ON = 2
OUTLIER_CUTOFF = 0.01

extractor = AppearanceExtractor(0, 0, TEST_SEASONS, AUGMENTATION_CUTS, AUGMENTATION_MIN_CUTS_ON, OUTLIER_CUTOFF)
train_input, train_output = extractor.get_train_data()
non_mol = [data[0] for data, label in zip(train_input, train_output) if label == 0.0]
mol = [data[0] for data, label in zip(train_input, train_output) if label == 1.0]

plt.figure(figsize=(12, 3))
plt.xlabel("Relative Appearance")
plt.ylabel("Is 'mol'")
plt.yticks(np.linspace(0.0, 1.0, 11))
plt.gcf().subplots_adjust(bottom = 0.15)

non_mol_kde = InnerAppearanceLayer.kernel_density_estimation(non_mol)
mol_kde = InnerAppearanceLayer.kernel_density_estimation(mol)
x = InnerAppearanceLayer.get_boundary(non_mol_kde, mol_kde, 10, 0.005, InnerAppearanceLayer.MIN_VALUE,
                                      InnerAppearanceLayer.MAX_VALUE)
plt.axvline(x = x, c = 'black')
x = InnerAppearanceLayer.get_boundary(non_mol_kde, mol_kde, 10, 0.995, InnerAppearanceLayer.MIN_VALUE,
                                      InnerAppearanceLayer.MAX_VALUE)
plt.axvline(x = x, c = 'black')
X = np.linspace(-3.0, 2.0, 500)
non_mol_Y = [non_mol_kde.pdf([x]) for x in X]
mol_Y = [mol_kde.pdf([x]) for x in X]
posterior_Y = [(mY / 10) / (9 * nY / 10 + mY / 10) for nY, mY in zip(non_mol_Y, mol_Y)]
plt.plot(X, non_mol_Y, color = 'g')
plt.plot(X, mol_Y, color = 'r')
plt.plot(X, posterior_Y, color = 'b')
plt.show()